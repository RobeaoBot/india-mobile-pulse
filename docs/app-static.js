/**
 * India Mobile Pulse - 静态版前端
 * 读取本地 JSON 文件渲染 Dashboard（无需后端）
 */

const state = {
    currentSource: '',
    currentPeriod: 'all',
    currentBrand: '',
    allPosts: [],
    dashboardData: null,
};

// ============================================================
// 数据加载
// ============================================================

async function loadJSON(path) {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`Load failed: ${res.status}`);
    return res.json();
}

async function loadDashboard() {
    try {
        const [dashboard, postsData, brandsData] = await Promise.all([
            loadJSON('dashboard.json'),
            loadJSON('posts.json'),
            loadJSON('brands.json'),
        ]);

        state.dashboardData = dashboard;
        state.allPosts = postsData.posts || [];

        renderStats(dashboard.stats);
        renderAnalysis(dashboard.latest_analysis);
        renderBrands(brandsData.brands || {});
        renderPosts(filterPosts(state.allPosts));
        renderRuns(dashboard.recent_runs || []);
        renderBrandFilter(brandsData.brands || {});
        updateLastTime(dashboard.last_updated);
    } catch (e) {
        console.error('Dashboard load failed:', e);
        showToast('加载失败，请稍后刷新');
    }
}

// ============================================================
// 帖子筛选（前端本地筛选，不需要 API）
// ============================================================

function filterPosts(posts) {
    let filtered = posts;

    if (state.currentSource) {
        filtered = filtered.filter(p => p.source === state.currentSource);
    }

    if (state.currentBrand) {
        filtered = filtered.filter(p => {
            const brands = safeParse(p.brands, []);
            return brands.includes(state.currentBrand);
        });
    }

    if (state.currentPeriod !== 'all') {
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const yesterday = new Date(today.getTime() - 86400000);
        const weekAgo = new Date(today.getTime() - 7 * 86400000);

        filtered = filtered.filter(p => {
            const d = new Date(p.published_at || p.collected_at);
            if (state.currentPeriod === 'today') return d >= today;
            if (state.currentPeriod === 'yesterday') return d >= yesterday && d < today;
            if (state.currentPeriod === 'week') return d >= weekAgo;
            return true;
        });
    }

    return filtered;
}

// ============================================================
// Render 函数（和原版相同）
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

function renderAnalysis(analysis) {
    const container = document.getElementById('analysisContent');
    const timeEl = document.getElementById('analysisTime');

    if (!analysis) {
        container.innerHTML = '<div class="empty-state">暂无分析报告，数据将在下次采集后自动生成</div>';
        timeEl.textContent = '--';
        return;
    }

    timeEl.textContent = formatTime(analysis.created_at);

    let html = '';

    if (analysis.summary) {
        html += '<div class="analysis-summary">' + escapeHtml(analysis.summary) + '</div>';
    }

    html += '<div class="analysis-grid">';

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

    const insights = safeParse(analysis.key_insights, []);
    if (insights.length > 0) {
        html += '<div class="analysis-card"><h3>💡 关键洞察</h3>';
        insights.forEach(function(ins) {
            html += '<div class="insight-item">' + escapeHtml(ins) + '</div>';
        });
        html += '</div>';
    }

    const keywords = safeParse(analysis.trending_keywords, []);
    if (keywords.length > 0) {
        html += '<div class="analysis-card"><h3>📈 热门关键词</h3><div class="keywords-cloud">';
        keywords.forEach(function(kw) {
            html += '<span class="keyword-tag">' + escapeHtml(kw) + '</span>';
        });
        html += '</div></div>';
    }

    html += '</div>';

    const provider = analysis.provider || 'rule';
    const providerLabel = provider === 'rule' ? '规则引擎' :
        provider === 'openai_compatible' ? 'LLM (OpenAI)' :
        provider === 'gemini' ? 'LLM (Gemini)' : provider;
    html += '<div style="text-align:right;font-size:11px;color:var(--text-muted);margin-top:12px;">分析引擎: ' + providerLabel + '</div>';

    container.innerHTML = html;
}

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

function updateLastTime(timestamp) {
    const el = document.getElementById('lastUpdate');
    if (timestamp) {
        const d = new Date(timestamp);
        el.textContent = '更新于 ' + d.toLocaleString('zh-CN');
    } else {
        el.textContent = '更新于 ' + new Date().toLocaleTimeString('zh-CN');
    }

    const scheduleEl = document.getElementById('nextSchedule');
    scheduleEl.textContent = '⏰ 每日自动采集';
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
    loadDashboard();

    // Refresh button
    document.getElementById('btnRefresh').addEventListener('click', function() {
        loadDashboard();
        showToast('数据已刷新');
    });

    // Source tabs
    document.getElementById('sourceTabs').addEventListener('click', function(e) {
        if (e.target.classList.contains('tab')) {
            document.querySelectorAll('#sourceTabs .tab').forEach(function(t) { t.classList.remove('active'); });
            e.target.classList.add('active');
            state.currentSource = e.target.dataset.source;
            renderPosts(filterPosts(state.allPosts));
        }
    });

    // Period tabs
    document.getElementById('periodTabs').addEventListener('click', function(e) {
        if (e.target.classList.contains('tab')) {
            document.querySelectorAll('#periodTabs .tab').forEach(function(t) { t.classList.remove('active'); });
            e.target.classList.add('active');
            state.currentPeriod = e.target.dataset.period;
            renderPosts(filterPosts(state.allPosts));
        }
    });

    // Brand filter
    document.getElementById('brandFilter').addEventListener('change', function(e) {
        state.currentBrand = e.target.value;
        renderPosts(filterPosts(state.allPosts));
    });
});
