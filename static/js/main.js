/**
 * 武鸣招聘 - 主JavaScript文件
 * 包含复制、收藏、聊天、AI对话、微信兼容等功能
 */

// ====== 微信浏览器检测与兼容 ======
(function(){
    var ua = navigator.userAgent.toLowerCase();
    var isWechat = ua.indexOf('micromessenger') !== -1;
    if (isWechat) {
        // 标记微信环境
        document.documentElement.classList.add('wx');
        // 微信X5强制最小字体 -> 用JS覆盖，作用于所有卡片内容
        var html = document.documentElement;
        html.style.setProperty('-webkit-text-size-adjust', 'none', 'important');
        html.style.setProperty('text-size-adjust', 'none', 'important');
        // 对卡片内小字单独设置 text-size-adjust
        var style = document.createElement('style');
        style.textContent = '.wx .job-meta, .wx .job-desc, .wx .company-link, .wx .job-location, .wx .tag, .wx .job-footer { -webkit-text-size-adjust: none !important; text-size-adjust: none !important; }';
        document.head.appendChild(style);
        // 微信X5底部安全区补偿（X5不支持env）
        var nav = document.querySelector('.nav');
        if (nav) {
            // 检测是否真的需要安全区（iPhone X+ 在微信X5里）
            var needsSafeArea = window.innerHeight > 700 && window.devicePixelRatio >= 2;
            if (needsSafeArea) {
                nav.style.paddingBottom = '20px';
            }
        }
        // 禁用微信下拉露出网页来源（仅阻止垂直下拉，不影响水平滑动轮播）
        var touchStartY = 0;
        document.body.addEventListener('touchstart', function(e){
            touchStartY = e.touches[0].clientY;
        }, {passive: true});
        document.body.addEventListener('touchmove', function(e){
            // 只阻止垂直方向的下拉（scrollTop<=0时的下拉）
            var deltaY = e.touches[0].clientY - touchStartY;
            var isVertical = Math.abs(e.touches[0].clientX - (e._startX || e.touches[0].clientX)) < Math.abs(deltaY) * 0.7;
            e._startX = e.touches[0].clientX;
            if (isVertical && deltaY > 0 && document.documentElement.scrollTop <= 0) {
                e.preventDefault();
            }
        }, {passive: false});
        // 微信打开时隐藏页面顶部网址栏
        window.scrollTo(0, 0);
    }
})();

// ====== 复制文本到剪贴板 ======
function copyText(text, btn) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function() {
            showTip(btn, '✅ 已复制到剪贴板', '#00b894');
        }).catch(function() {
            fallbackCopy(text, btn);
        });
    } else {
        fallbackCopy(text, btn);
    }
}

function fallbackCopy(text, btn) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0;';
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch(e) {}
    document.body.removeChild(ta);
    if (ok) { showTip(btn, '✅ 已复制到剪贴板', '#00b894'); }
    else { showTip(btn, '⚠️ 请长按选择复制', '#e17055'); }
}

function showTip(btn, msg, color) {
    var tip = document.createElement('div');
    tip.textContent = msg;
    tip.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:'+
        color+';color:white;padding:10px 20px;border-radius:8px;font-size:14px;z-index:9999;'+
        'box-shadow:0 4px 12px rgba(0,0,0,0.3);transition:opacity 0.3s;max-width:90%;text-align:center;';
    document.body.appendChild(tip);
    setTimeout(function() { tip.style.opacity='0'; setTimeout(function(){ tip.remove(); },300); }, 1500);
}

// ====== 复制岗位信息 ======
function copyJob(e, id, title, company, salary, phone) {
    e.stopPropagation(); e.preventDefault();
    var text = '【' + title + '】' + company + ' | ' + salary;
    if (phone) text += ' | 📞 ' + phone;
    text += ' 🏭武鸣招聘';
    var ta = document.createElement('textarea');
    ta.value = text; ta.style.cssText='position:fixed;left:-9999px;top:0;opacity:0;';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); var btn=e.target; var old=btn.innerHTML; btn.innerHTML='✅ 已复制'; setTimeout(function(){btn.innerHTML=old;},2000); }
    catch(err) { prompt('请手动复制👇', text); }
    document.body.removeChild(ta);
}

// ====== 收藏功能 ======
async function toggleFav(e, jobId, btn) {
    e.stopPropagation();
    try {
        const res = await fetch('/api/favorites/' + jobId, {method:'POST'});
        const data = await res.json();
        if (data.error) { alert(data.error); return; }
        btn.textContent = data.favorited ? '❤️' : '🤍';
        btn.title = data.favorited ? '取消收藏' : '收藏';
    } catch(err) { console.error(err); }
}

// 页面加载时标记已收藏的岗位
(async function(){
    try {
        const res = await fetch('/api/favorites');
        const data = await res.json();
        if (data.favorites) {
            data.favorites.forEach(function(jid) {
                const btn = document.querySelector('.fav-btn[data-job-id="'+jid+'"]');
                if (btn) { btn.textContent = '❤️'; btn.title = '取消收藏'; }
            });
        }
    } catch(e) {}
})();

// ====== 分享岗位 ======
function shareJob(e, title, company, salary, location) {
    e.stopPropagation(); e.preventDefault();
    var text = '【' + title + '】' + company + ' | ' + salary + ' | ' + location + ' 🏭武鸣招聘';
    if (navigator.share) { navigator.share({title:title+'-'+company, text:text}).catch(function(){}); }
    else { copyJob(e,'',title,company,salary,''); }
}

// ====== 全局 send() 保底 ======
(function(){
    window.send = function() {
        try {
            var inp = document.getElementById('inp');
            if (!inp) return;
            var txt = inp.value.trim();
            if (!txt) return;
            var msgs = document.getElementById('msgs');
            if (msgs) {
                var div = document.createElement('div');
                div.className = 'msg mine';
                div.innerHTML = txt + '<div class="time">刚刚</div>';
                msgs.appendChild(div);
                msgs.scrollTop = msgs.scrollHeight;
            }
            inp.value = '';
            var convId = window.convId || 0;
            var myType = window.myType || 'guest';
            var myId = window.myId || 0;
            fetch('/api/chat/send', {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({conversation_id:convId, content:txt, sender_type:myType, sender_id:myId})
            }).then(function(r){return r.json();}).then(function(d){
                if(d && d.time){ var t=div.querySelector('.time'); if(t) t.textContent=d.time.substring(11,16); }
            }).catch(function(e){console.warn('send error',e);});
            if(convId) fetch('/api/chat/'+convId+'/read',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reader_type:myType})});
        } catch(e) { console.error('send error', e); }
    };
    function bindChat() {
        if(document.getElementById('chatInput')) return;
        var btn = document.getElementById('sendBtn');
        var inp = document.getElementById('inp');
        if(btn) { btn.onclick = function(e){e.preventDefault();window.send();}; }
        if(inp) { inp.addEventListener('keydown', function(e){if(e.key==='Enter'){e.preventDefault();window.send();}}); }
    }
    if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', bindChat);
    else setTimeout(bindChat, 0);
})();
