# 第三方组件

## Chart.js

- **版本**: 4.4.0
- **用途**: 仪表盘图表渲染（饼图 / 折线图 / 柱状图 / 雷达图）
- **许可**: MIT License © 2023 Chart.js Contributors
- **官网**: https://www.chartjs.org
- **来源**: `https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js`

本文件由 npm 包 `chart.js@4.4.0` 的 `dist/chart.umd.js` 复制而来（该文件本身已是压缩版本），
并移除了末尾的 `sourceMappingURL` 注释，避免浏览器发起多余请求。

### 为什么内联

仪表盘 HTML 需要**完全离线可用**——生成后双击即可看图，不依赖任何 CDN。
若外链 CDN，在离线、内网或 CDN 不可达的环境下所有图表会是空白，
这与本项目"100% 本地运行"的承诺相矛盾。

代价是每个 HTML 约增加 200 KB（可接受：单文件、可自由分享、无外部依赖）。
