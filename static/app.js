/**
 * India Mobile Pulse - Frontend App
 * Dashboard 交互逻辑
 */

// ============================================================
// State
// ============================================================

const state = {
    currentSource: '',
    currentPeriod: 'all',
    currentBrand: '',
    dashboardData: null,
};

// ============================================================
// API
// ============================================================

async function api(path, method = 'GET') {
    const res = await fetch(path, { method });
    if (!res.ok) throw new Error(`API Error: ${res.status}`);
    return res.json();
}

// ============================================================
// Dashboard
// ============================================================

async function loadDashboard() {
    try {
        const data = await api('/api/dashboard');
        state.dashboardData = data;
        renderStats(data.stats);
        renderAnalysis(data.latest_analysis);
        renderBrands(data.stats.brand_mentions || {});
        renderPosts(data.recent_posts || []);
        renderRuns(data.recent_runs || []);
        renderBrandFilter(data.stats.brand_mentions || {});
        updateLastTime();
        updateNextSchedule(data);
    } catch (e) {
        console.error('Dashboard load failed:', e);
        showToast('加载失败，请检查后端服务');
    }
}

// ============================================================
// Render: Stats
// ============================================================

function renderStats(stats) {
    document.getElementById('statTotal').textContent = stats.total || 0;
    document.getElementById('statToday').textContent = stats.today || 0;
    document.getElementById('statBrands').textContent =
        Object.keys(stats.brand_mentions || {}).length;

    const sent = stats.sentiment || {};
    const total = (sent.positive || 0) + (sent.negative || 0) + (sent.neutral || 0);
    if (total > 0) {
        const posPct = Math.round((sent.positive || 0) / total * 100);
        const el = document.getElementById('statSentiment');
        if (posPct >= 50) {
            el.innerHTML = '<span style="color:var(--green)">😊 ' + posPct + '%</span>';
        } else if (posPct >= 30) {
            el.innerHTML = '<span style="color:var(--yellow)">😐 ' + posPct + '%</span>';
        } else {
            el.innerHTML = '<span style="color:var(--red)">😟 ' + posPct + '%</span>';
        }
    } else {
        document.getElementById('statSentiment').textContent = '--';
    }
}

// ============================================================
// Render: Analysis
// ============================================================

function renderAnalysis(analysis) {
    const container = document.getElementById('analysisContent');
    const timeEl = document.getElementById('analysisTime');

    if (!analysis) {
        container.innerHTML = '<div class="empty-state">暂无分析报告，点击「分析」按钮生成</div>';
        timeEl.textContent = '--';
        return;
    }

    timeEl.textContent = formatTime(analysis.created_at);

    let html = '';

    // Summary
    if (analysis.summary) {
        html += '<div class="analysis-summary">' + escapeHtml(analysis.summary) + '</div>';
    }

    // Grid
    html += '<div class="analysis-grid">';

    // Hot Topics
    const topics = safeParse(analysis.hot_topics, []);
    if (topics.length > 0) {
        html += '<div class="analysis-card"><h3>🔥 热门话题</h3>';
        topics.forEach(function(t) {
            const heat = t.heat || 'low';
            const heatLabel = heat === 'high' ? '热' : heat === 'medium' ? '温' : '冷';
            html += '<div class="hot-topic-item">' +
                '<span class="heat-badge heat-' + heat + '">' + heatLabel + '</span>' +
                '<div>' +
                '<div class="topic-name">' + escapeHtml(t.topic || t) + '</div>' +
                (t.description ? '<div class="topic-desc">' + escapeHtml(t.description) + '</div>' : '') +
                '</div></div>';
        });
        html += '</div>';
    }

    // Brand Sentiment
    const brandSent = safeParse(analysis.brand_sentiment, {});
    const brandKeys = Object.keys(brandSent);
    if (brandKeys.length > 0) {
        html += '<div class="analysis-card"><h3>🏷️ 品牌情感</h3>';
        brandKeys.forEach(function(brand) {
            const info = brandSent[brand];
            const sentiment = info.sentiment || 'neutral';
            const reason = info.reason || '';
            html += '<div class="brand-sentiment-item">' +
                '<span>' + escapeHtml(brand) + '</span>' +
                '<span class="sentiment-badge sentiment-' + sentiment + '">' + sentimentLabel(sentiment) + '</span>' +
                '</div>' +
                (reason ? '<div style="font-size:11px;color:var(--text-muted);margin-top:-4px;margin-bottom:4px;">' + escapeHtml(reason) + '</div>' : '');
        });
        html += '</div>';
    }

    // Key Insights
    const insights = safeParse(analysis.key_insights, []);
    if (insights.length > 0) {
        html += '<div class="analysis-card"><h3>💡 关键洞察</h3>';
        insights.forEach(function(ins) {
            html += '<div class="insight-item">' + escapeHtml(ins) + '</div>';
        });
        html += '</div>';
    }

    // Trending Keywords
    const keywords = safeParse(analysis.trending_keywords, []);
    if (keywords.length > 0) {
        html += '<div class="analysis-card"><h3>📈 热门关键词</h3><div class="keywords-cloud">';
        keywords.forEach(function(kw) {
            html += '<span class="keyword-tag">' + escapeHtml(kw) + '</span>';
        });
        html += '</div></div>';
    }

    html += '</div>';

    // Provider badge
    const provider = analysis.provider || 'rule';
    const providerLabel = provider === 'rule' ? '规则引擎' :
        provider === 'openai_compatible' ? 'LLM (OpenAI)' :
        provider === 'gemini' ? 'LLM (Gemini)' : provider;
    html += '<div style="text-align:right;font-size:11px;color:var(--text-muted);margin-top:12px;">分析引擎: ' + providerLabel + '</div>';

    container.innerHTML = html;
}

// ============================================================
// Render: Brands Chart
// ============================================================

const BRAND_COLORS = [
    '#58a6ff', '#3fb950', '#d29922', '#f85149', '#bc8cff',
    '#f778ba', '#79c0ff', '#56d4dd', '#e3b341', '#ffa657',
    '#ff7b72', '#7ee787', '#a5d6ff', '#d2a8ff', '#ffc680',
];

function renderBrands(brandMentions) {
    const container = document.getElementById('brandsChart');
    const entries = Object.entries(brandMentions);

    if (entries.length === 0) {
        container.innerHTML = '<div class="empty-state">暂无数据</div>';
        return;
    }

    const maxCount = entries[0][1];
    let html = '';

    entries.forEach(function(entry, i) {
        const brand = entry[0], count = entry[1];
        const pct = Math.max(4, (count / maxCount) * 100);
        const color = BRAND_COLORS[i % BRAND_COLORS.length];
        html += '<div class="brand-bar-row">' +
            '<span class="brand-bar-name">' + escapeHtml(brand) + '</span>' +
            '<div class="brand-bar-track">' +
            '<div class="brand-bar-fill" style="width:' + pct + '%;background:' + color + '"></div>' +
            '</div>' +
            '<span class="brand-bar-count">' + count + '</span>' +
            '</div>';
    });

    container.innerHTML = html;
}

// ============================================================
// Render: Posts
// ============================================================

function renderPosts(posts) {
    const container = document.getElementById('postsList');

    if (!posts || posts.length === 0) {
        container.innerHTML = '<div class="empty-state">暂无帖子数据</div>';
        return;
    }

    let html = '';
    posts.forEach(function(p) {
        const sourceClass = 'source-' + p.source;
        const sourceLabels = { reddit: 'R', youtube: 'YT', news: 'N', official: 'OFF' };
        const sourceLabel = sourceLabels[p.source] || '?';
        const brands = safeParse(p.brands, []);
        const osTags = safeParse(p.os_tags, []);
        const hwTags = safeParse(p.hardware_tags, []);
        const sentClass = p.sentiment || 'neutral';

        html += '<a href="' + escapeHtml(p.url || '#') + '" target="_blank" rel="noopener" class="post-item" style="text-decoration:none;color:inherit">' +
            '<div class="post-source-badge ' + sourceClass + '">' + sourceLabel + '</div>' +
            '<div class="post-body">' +
            '<div class="post-title">' + escapeHtml(p.title) + '</div>' +
            '<div class="post-meta">' +
            '<span class="sentiment-dot ' + sentClass + '"></span>' +
            '<span>' + escapeHtml(p.author || '') + '</span>' +
            (p.score ? '<span class="post-score">▲ ' + p.score + '</span>' : '') +
            '<span>' + formatTime(p.published_at || p.collected_at) + '</span>' +
            '</div>' +
            '<div class="post-brands">' +
            brands.map(function(b) { return '<span class="brand-tag">' + escapeHtml(b) + '</span>'; }).join('') +
            osTags.map(function(o) { return '<span class="brand-tag os-tag">' + escapeHtml(o) + '</span>'; }).join('') +
            hwTags.slice(0, 3).map(function(h) { return '<span class="brand-tag hw-tag">' + escapeHtml(h) + '</span>'; }).join('') +
            '</div>' +
            '</div></a>';
    });

    container.innerHTML = html;
}

// ============================================================
// Render: Runs
// ============================================================

function renderRuns(runs) {
    const container = document.getElementById('runsList');

    if (!runs || runs.length === 0) {
        container.innerHTML = '<div class="empty-state">暂无记录</div>';
        return;
    }

    let html = '';
    runs.forEach(function(r) {
        const statusClass = r.status === 'success' ? 'run-success' : 'run-error';
        const statusText = r.status === 'success' ? '✓ ' + (r.new_posts || 0) + '条新增' : '✗ 失败';
        html += '<div class="run-item">' +
            '<span class="run-source">' + escapeHtml(r.source) + '</span>' +
            '<span>' + (r.posts_count || 0) + '条</span>' +
            '<span class="run-status ' + statusClass + '">' + statusText + '</span>' +
            '<span class="run-time">' + formatTime(r.started_at) + '</span>' +
            '</div>';
    });

    container.innerHTML = html;
}

// ============================================================
// Render: Brand Filter
// ============================================================

function renderBrandFilter(brandMentions) {
    const select = document.getElementById('brandFilter');
    const brands = Object.keys(brandMentions);

    select.innerHTML = '<option value="">全部品牌</option>';
    brands.forEach(function(b) {
        const opt = document.createElement('option');
        opt.value = b;
        opt.textContent = b + ' (' + brandMentions[b] + ')';
        select.appendChild(opt);
    });
}

// ============================================================
// Filter Posts
// ============================================================

async function loadFilteredPosts() {
    try {
        const params = new URLSearchParams();
        if (state.currentSource) params.set('source', state.currentSource);
        if (state.currentBrand) params.set('brand', state.currentBrand);
        params.set('period', state.currentPeriod);
        params.set('limit', '50');

        const data = await api('/api/posts?' + params.toString());
        renderPosts(data.posts || []);
    } catch (e) {
        console.error('Filter failed:', e);
    }
}

// ============================================================
// Actions
// ============================================================

async function triggerCollect() {
    const btn = document.getElementById('btnCollect');
    btn.disabled = true;
    showToast('开始采集...');
    try {
        await api('/api/collect', 'POST');
        showToast('采集任务已启动，约10秒后刷新');
        setTimeout(function() { loadDashboard(); btn.disabled = false; }, 10000);
    } catch (e) {
        showToast('采集启动失败');
        btn.disabled = false;
    }
}

async function triggerAnalyze() {
    const btn = document.getElementById('btnAnalyze');
    btn.disabled = true;
    showToast('开始分析...');
    try {
        await api('/api/analyze', 'POST');
        showToast('分析任务已启动，约15秒后刷新');
        setTimeout(function() { loadDashboard(); btn.disabled = false; }, 15000);
    } catch (e) {
        showToast('分析启动失败');
        btn.disabled = false;
    }
}

// ============================================================
// Utilities
// ============================================================

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function safeParse(val, fallback) {
    if (!val) return fallback;
    if (typeof val === 'string') {
        try { return JSON.parse(val); }
        catch (e) { return fallback; }
    }
    return val;
}

function sentimentLabel(s) {
    const labels = { positive: '正面', negative: '负面', neutral: '中性' };
    return labels[s] || s;
}

function formatTime(ts) {
    if (!ts) return '--';
    try {
        const d = new Date(ts);
        const now = new Date();
        const diff = (now - d) / 1000;

        if (diff < 60) return '刚刚';
        if (diff < 3600) return Math.floor(diff / 60) + '分钟前';
        if (diff < 86400) return Math.floor(diff / 3600) + '小时前';
        if (diff < 604800) return Math.floor(diff / 86400) + '天前';

        return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch (e) {
        return ts;
    }
}

function updateLastTime() {
    const el = document.getElementById('lastUpdate');
    el.textContent = '更新于 ' + new Date().toLocaleTimeString('zh-CN');
}

function updateNextSchedule(data) {
    const el = document.getElementById('nextSchedule');
    const schedulerInfo = data.scheduler;
    if (!schedulerInfo || !schedulerInfo.jobs) {
        el.textContent = '';
        return;
    }
    const dailyJob = schedulerInfo.jobs.find(function(j) { return j.id === 'daily_collect_and_analyze'; });
    if (dailyJob && dailyJob.next_run) {
        const next = new Date(dailyJob.next_run);
        el.textContent = '⏰ 下次自动采集: ' + next.toLocaleString('zh-CN', {
            month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
        });
    }
}

function showToast(msg) {
    const toast = document.getElementById('toast');
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(function() { toast.classList.remove('show'); }, 3000);
}

// ============================================================
// Event Bindings
// ============================================================

document.addEventListener('DOMContentLoaded', function() {
    // Load dashboard
    loadDashboard();

    // Auto refresh every 5 minutes
    setInterval(loadDashboard, 300000);

    // Refresh button
    document.getElementById('btnRefresh').addEventListener('click', loadDashboard);

    // Collect button
    document.getElementById('btnCollect').addEventListener('click', triggerCollect);

    // Analyze button
    document.getElementById('btnAnalyze').addEventListener('click', triggerAnalyze);

    // Source tabs
    document.getElementById('sourceTabs').addEventListener('click', function(e) {
        if (e.target.classList.contains('tab')) {
            document.querySelectorAll('#sourceTabs .tab').forEach(function(t) { t.classList.remove('active'); });
            e.target.classList.add('active');
            state.currentSource = e.target.dataset.source;
            loadFilteredPosts();
        }
    });

    // Period tabs
    document.getElementById('periodTabs').addEventListener('click', function(e) {
        if (e.target.classList.contains('tab')) {
            document.querySelectorAll('#periodTabs .tab').forEach(function(t) { t.classList.remove('active'); });
            e.target.classList.add('active');
            state.currentPeriod = e.target.dataset.period;
            loadFilteredPosts();
        }
    });

    // Brand filter
    document.getElementById('brandFilter').addEventListener('change', function(e) {
        state.currentBrand = e.target.value;
        loadFilteredPosts();
    });
});
