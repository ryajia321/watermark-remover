// pages/index/index.js - 去水印解析首页
const app = getApp();

const HISTORY_KEY = 'wm_history';
const PREVIEW_KEY = 'wm_preview';
const MAX_HISTORY = 20;

// 按域名粗略识别平台，仅做输入提示用（不影响解析，后端会再次判定）
const PLATFORM_PATTERNS = [
  { id: 'douyin', name: '抖音', re: /douyin\.com|iesdouyin\.com|v\.douyin\.com/ },
  { id: 'kuaishou', name: '快手', re: /kuaishou\.com|v\.kuaishou\.com|chenzhongtech\.com/ },
  { id: 'xiaohongshu', name: '小红书', re: /xiaohongshu\.com|xhslink\.com/ },
  { id: 'bilibili', name: '哔哩哔哩', re: /bilibili\.com|b23\.tv|acg\.tv/ },
  { id: 'weibo', name: '微博', re: /weibo\.(com|cn)|t\.cn/ },
  { id: 'wechat', name: '微信视频号', re: /channels\.weixin|weixin\.qq\.com/ },
  { id: 'pipixia', name: '皮皮虾', re: /pipix\.com|hulushequ\.com/ },
];

function extractUrl(text) {
  const m = String(text || '').match(/https?:\/\/[^\s"'<>]+/);
  return m ? m[0] : '';
}

function detectPlatformName(url) {
  const hit = PLATFORM_PATTERNS.find((p) => p.re.test(url));
  return hit ? hit.name : '';
}

function saveHistory(result) {
  try {
    let list = wx.getStorageSync(HISTORY_KEY);
    if (!Array.isArray(list)) list = [];
    list.unshift({
      title: result.title || '未命名视频',
      platform: result.platform || '',
      platform_name: result.platform_name || '',
      author: result.author || '',
      cover: result.cover || '',
      video_url: result.video_url || '',
      sourceUrl: result.sourceUrl || '',
      time: Date.now(),
    });
    wx.setStorageSync(HISTORY_KEY, list.slice(0, MAX_HISTORY));
  } catch (e) {}
}

Page({
  data: {
    inputUrl: '',
    platformHint: '',
    loading: false,
    result: null,
    bannerAdId: '', // 有配置才显示 Banner
  },

  onLoad() {
    const cfg = (getApp().globalData && getApp().globalData.adConfig) || {};
    if (cfg.bannerId) this.setData({ bannerAdId: cfg.bannerId });
  },

  onShow() {
    // 1）从历史页点进来查看某条记录（history 页先写入 wm_preview 再 switchTab）
    try {
      const preview = wx.getStorageSync(PREVIEW_KEY);
      if (preview && preview.video_url) {
        wx.removeStorageSync(PREVIEW_KEY);
        this.setData({ result: preview, inputUrl: preview.sourceUrl || '' });
        return;
      }
    } catch (e) {}

    // 2）剪贴板自动识别：输入框为空时尝试读取（失败则静默跳过）
    if (!this.data.inputUrl) {
      wx.getClipboardData({
        success: (res) => {
          const url = extractUrl(res.data);
          if (url && !this.data.inputUrl) {
            this.setData({ inputUrl: url, platformHint: detectPlatformName(url) });
          }
        },
        fail: () => {},
      });
    }
  },

  onInput(e) {
    const v = e.detail.value;
    this.setData({ inputUrl: v, platformHint: detectPlatformName(extractUrl(v)) });
  },

  onClear() {
    this.setData({ inputUrl: '', platformHint: '', result: null });
  },

  /** 一键粘贴：从剪贴板提取链接 */
  onPaste() {
    wx.getClipboardData({
      success: (res) => {
        const url = extractUrl(res.data);
        if (url) {
          this.setData({ inputUrl: url, platformHint: detectPlatformName(url) });
        } else {
          app.showError('剪贴板中没有找到有效链接');
        }
      },
      fail: () => app.showError('读取剪贴板失败'),
    });
  },

  /**
   * 去水印解析（入口）。
   * 若配置了激励视频广告位，先看广告、看完才真正解析；
   * 未配置广告位则直接解析（开发/测试阶段）。
   */
  onParse() {
    const url = extractUrl(this.data.inputUrl);
    if (!url) {
      app.showError('请先粘贴有效的视频分享链接');
      return;
    }
    const cfg = (app.globalData && app.globalData.adConfig) || {};
    const adUnitId = cfg.rewardedVideoId || '';
    if (!adUnitId) {
      this.doParseRequest(url);
      return;
    }
    const ad = this.ensureRewardedAd(adUnitId);
    if (!ad) {
      this.doParseRequest(url);
      return;
    }
    // 看完广告后的回调
    this._adCb = () => this.doParseRequest(url);
    ad.show().catch(() => {
      // show 失败时尝试先 load 再 show
      ad.load()
        .then(() => ad.show())
        .catch(() => {
          // 广告实在加载不出来也不挡路，直接解析
          const cb = this._adCb;
          this._adCb = null;
          if (cb) cb();
        });
    });
  },

  /** 创建（或复用）激励视频广告实例 */
  ensureRewardedAd(adUnitId) {
    if (this._rewardedAd) return this._rewardedAd;
    if (typeof wx.createRewardedVideoAd !== 'function') return null;
    try {
      const ad = wx.createRewardedVideoAd({ adUnitId });
      ad.onError(() => {
        // 广告加载失败：放行本次解析
        const cb = this._adCb;
        this._adCb = null;
        if (cb) cb();
      });
      ad.onClose((res) => {
        const cb = this._adCb;
        this._adCb = null;
        if (res && res.isEnded) {
          if (cb) cb();
        } else {
          app.showError('需要观看完整视频才能免费解析哦');
        }
      });
      this._rewardedAd = ad;
      return ad;
    } catch (e) {
      return null;
    }
  },

  /** 真正发起解析请求 */
  doParseRequest(url) {
    this.setData({ loading: true, result: null });
    wx.showLoading({ title: '解析中...', mask: true });

    app
      .request({ url: '/api/parse', method: 'POST', data: { url } })
      .then((data) => {
        wx.hideLoading();
        this.setData({ loading: false });
        if (data && data.ok && data.video_url) {
          const result = Object.assign({}, data, { sourceUrl: url });
          this.setData({ result });
          saveHistory(result);
        } else {
          app.showError((data && data.error) || '解析失败，请稍后重试');
        }
      })
      .catch((err) => {
        wx.hideLoading();
        this.setData({ loading: false });
        app.showError((err && err.message) || '解析失败，请稍后重试');
      });
  },

  /** 保存视频到相册（含授权引导） */
  onSaveVideo() {
    const videoUrl = this.data.result && this.data.result.video_url;
    if (!videoUrl) {
      app.showError('没有可保存的视频');
      return;
    }
    wx.getSetting({
      success: (res) => {
        if (res.authSetting['scope.writePhotosAlbum']) {
          this.downloadAndSave(videoUrl);
        } else {
          wx.authorize({
            scope: 'scope.writePhotosAlbum',
            success: () => this.downloadAndSave(videoUrl),
            fail: () => {
              // 用户拒绝或之前已拒绝：引导去设置页手动开启
              wx.showModal({
                title: '需要相册权限',
                content: '保存视频需要「添加到相册」权限，请前往设置页开启。',
                confirmText: '去设置',
                cancelText: '取消',
                success: (r) => {
                  if (r.confirm) wx.openSetting({});
                },
              });
            },
          });
        }
      },
      fail: () => app.showError('获取授权状态失败'),
    });
  },

  downloadAndSave(videoUrl) {
    wx.showLoading({ title: '下载中...', mask: true });
    wx.downloadFile({
      url: videoUrl,
      success: (res) => {
        if (res.statusCode === 200) {
          wx.saveVideoToPhotosAlbum({
            filePath: res.tempFilePath,
            success: () => {
              wx.hideLoading();
              app.showSuccess('已保存到相册');
            },
            fail: () => {
              wx.hideLoading();
              app.showError('保存到相册失败，请重试');
            },
          });
        } else {
          wx.hideLoading();
          app.showError('视频下载失败（HTTP ' + res.statusCode + '）');
        }
      },
      fail: () => {
        wx.hideLoading();
        app.showError('视频下载失败，请检查网络');
      },
    });
  },

  /** 复制无水印直链 */
  onCopyLink() {
    const videoUrl = this.data.result && this.data.result.video_url;
    if (!videoUrl) {
      app.showError('没有可复制的链接');
      return;
    }
    wx.setClipboardData({
      data: videoUrl,
      success: () => app.showSuccess('链接已复制'),
      fail: () => app.showError('复制失败'),
    });
  },

  /** Banner 广告加载失败时隐藏，避免占位 */
  onAdError() {
    this.setData({ bannerAdId: '' });
  },
});
