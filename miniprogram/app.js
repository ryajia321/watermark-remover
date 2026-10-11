// ============================================================
// 去水印小程序 - 全局逻辑
// ⚠️ 重要：project.config.json 中的 appid 仅为占位符，
//    导入微信开发者工具后请替换为你自己的小程序 AppID（详见 README.md）
// ============================================================

const DEFAULT_BASE_URL = 'https://api.example.com'; // 占位地址，请在「设置」页改为你的后端地址
const BASE_URL_KEY = 'wm_base_url';

App({
  globalData: {
    baseUrl: DEFAULT_BASE_URL,

    // ============ 广告变现配置（流量主）============
    // 开通流程：小程序发布上线后 → 微信公众平台 → 左侧「流量主」→ 开通
    // → 广告管理 → 新建广告位 → 把得到的 adunit-xxx 填到下面对应位置。
    // 留空则不显示广告、不影响正常使用（开发阶段请保持留空）。
    adConfig: {
      bannerId: '',         // Banner 广告位 ID，如 'adunit-xxxxxxxxxxxxxxxx'
      rewardedVideoId: '',  // 激励视频广告位 ID（解析前观看，看完免费解析一次）
      // interstitialId: '', // 插屏广告位 ID（可选，示例代码中未启用）
    },
  },

  onLaunch() {
    // 启动时读取用户保存过的后端接口地址
    try {
      const saved = wx.getStorageSync(BASE_URL_KEY);
      if (saved && typeof saved === 'string' && saved.trim()) {
        this.globalData.baseUrl = saved.trim().replace(/\/+$/, '');
      }
    } catch (e) {
      // 读取失败则使用默认值，不阻塞启动
    }
  },

  /**
   * 设置并持久化后端接口地址
   * @param {string} url 如 https://api.xxx.com
   */
  setBaseUrl(url) {
    const clean = String(url || '').trim().replace(/\/+$/, '');
    this.globalData.baseUrl = clean || DEFAULT_BASE_URL;
    try {
      wx.setStorageSync(BASE_URL_KEY, this.globalData.baseUrl);
    } catch (e) {}
  },

  /**
   * 统一网络请求封装（返回 Promise）
   * @param {{url: string, method?: string, data?: object}} opts
   */
  request(opts) {
    const { url, method = 'GET', data = {} } = opts || {};
    const base = String(this.globalData.baseUrl || DEFAULT_BASE_URL).replace(/\/+$/, '');
    return new Promise((resolve, reject) => {
      wx.request({
        url: base + url,
        method,
        data,
        header: { 'content-type': 'application/json' },
        timeout: 20000,
        success: (res) => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(res.data);
          } else {
            reject(new Error('请求失败（HTTP ' + res.statusCode + '），请检查接口地址'));
          }
        },
        fail: () => {
          reject(new Error('网络请求失败，请检查接口地址与网络连接'));
        },
      });
    });
  },

  /** 统一错误提示（中文） */
  showError(msg) {
    const text = String(msg || '操作失败，请稍后重试');
    wx.showToast({ title: text.length > 28 ? text.slice(0, 28) + '…' : text, icon: 'none', duration: 2500 });
  },

  /** 统一成功提示 */
  showSuccess(msg) {
    wx.showToast({ title: String(msg || '成功'), icon: 'success', duration: 1500 });
  },
});
