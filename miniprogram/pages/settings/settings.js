// pages/settings/settings.js - 接口配置 / 支持平台 / 使用说明 / 免责声明
const app = getApp();

// 后端不可用时的兜底平台列表（仅展示用）
const FALLBACK_PLATFORMS = [
  { id: 'douyin', name: '抖音' },
  { id: 'kuaishou', name: '快手' },
  { id: 'xiaohongshu', name: '小红书' },
  { id: 'bilibili', name: '哔哩哔哩' },
  { id: 'weibo', name: '微博' },
  { id: 'wechat', name: '微信视频号' },
  { id: 'pipixia', name: '皮皮虾' },
];

/** 兼容多种返回格式：字符串数组 / 对象数组 / {platforms:[...]} */
function normalizePlatforms(data) {
  let raw = [];
  if (Array.isArray(data)) raw = data;
  else if (data && Array.isArray(data.platforms)) raw = data.platforms;
  else if (data && Array.isArray(data.data)) raw = data.data;
  const list = raw
    .map((p) => {
      if (typeof p === 'string') return { id: p, name: p };
      if (p && typeof p === 'object') {
        return {
          id: String(p.id || p.platform || p.code || ''),
          name: String(p.name || p.platform_name || p.title || p.id || ''),
        };
      }
      return null;
    })
    .filter((p) => p && p.name);
  return list.length ? list : FALLBACK_PLATFORMS;
}

Page({
  data: {
    baseUrl: '',
    baseUrlInput: '',
    platforms: [],
    loadingPlatforms: false,
  },

  onShow() {
    const baseUrl = app.globalData.baseUrl || '';
    this.setData({ baseUrl, baseUrlInput: baseUrl });
    this.fetchPlatforms();
  },

  onInput(e) {
    this.setData({ baseUrlInput: e.detail.value });
  },

  /** 保存后端接口地址 */
  onSave() {
    const v = String(this.data.baseUrlInput || '').trim().replace(/\/+$/, '');
    if (!/^https?:\/\/[^\/\s]+/.test(v)) {
      app.showError('请输入正确的接口地址，如 https://api.xxx.com');
      return;
    }
    app.setBaseUrl(v);
    this.setData({ baseUrl: v, baseUrlInput: v });
    app.showSuccess('已保存');
    this.fetchPlatforms();
  },

  /** 恢复默认占位地址 */
  onReset() {
    wx.showModal({
      title: '恢复默认',
      content: '确定要恢复为默认占位地址吗？',
      success: (res) => {
        if (res.confirm) {
          try {
            wx.removeStorageSync('wm_base_url');
          } catch (e) {}
          app.globalData.baseUrl = 'https://api.example.com';
          this.setData({ baseUrl: app.globalData.baseUrl, baseUrlInput: app.globalData.baseUrl });
          app.showSuccess('已恢复默认');
        }
      },
    });
  },

  /** 拉取支持平台列表 */
  fetchPlatforms() {
    this.setData({ loadingPlatforms: true });
    app
      .request({ url: '/api/platforms' })
      .then((data) => {
        this.setData({ platforms: normalizePlatforms(data), loadingPlatforms: false });
      })
      .catch(() => {
        // 后端不可达时用兜底列表，保证页面可用
        this.setData({ platforms: FALLBACK_PLATFORMS, loadingPlatforms: false });
      });
  },
});
