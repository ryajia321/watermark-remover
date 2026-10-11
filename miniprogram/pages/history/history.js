// pages/history/history.js - 解析历史记录（本地最近 20 条）
const app = getApp();

const HISTORY_KEY = 'wm_history';
const PREVIEW_KEY = 'wm_preview';

function formatTime(ts) {
  const d = new Date(ts);
  const pad = (n) => String(n).padStart(2, '0');
  return (
    pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' +
    pad(d.getHours()) + ':' + pad(d.getMinutes())
  );
}

Page({
  data: {
    list: [],
  },

  onShow() {
    this.loadList();
  },

  loadList() {
    let list = [];
    try {
      list = wx.getStorageSync(HISTORY_KEY) || [];
      if (!Array.isArray(list)) list = [];
    } catch (e) {}
    list = list.map((item) => Object.assign({}, item, {
      timeText: item.time ? formatTime(item.time) : '',
    }));
    this.setData({ list });
  },

  /** 点击某条记录：回到首页展示（tabBar 页面用 switchTab，不支持传参，走临时缓存） */
  onItemTap(e) {
    const index = e.currentTarget.dataset.index;
    const item = this.data.list[index];
    if (!item || !item.video_url) {
      app.showError('该记录数据不完整');
      return;
    }
    try {
      wx.setStorageSync(PREVIEW_KEY, item);
    } catch (err) {}
    wx.switchTab({ url: '/pages/index/index' });
  },

  /** 清空历史记录（二次确认） */
  onClear() {
    wx.showModal({
      title: '确认清空',
      content: '确定要清空全部解析历史记录吗？',
      confirmText: '清空',
      confirmColor: '#e64340',
      success: (res) => {
        if (res.confirm) {
          try {
            wx.removeStorageSync(HISTORY_KEY);
          } catch (e) {}
          this.setData({ list: [] });
          app.showSuccess('已清空');
        }
      },
    });
  },
});
