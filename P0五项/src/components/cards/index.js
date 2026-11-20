/**
 * 卡片组件库出口。
 * 应用层只从本文件导入，不直接依赖内部文件路径；
 * 后续新增卡片（策略卡等）时在此追加导出。
 */
export { EventCardHTML, EVENT_KINDS, impactRow, artSource } from './EventCardView.js';
export { EventCardController } from './EventCardController.js';
