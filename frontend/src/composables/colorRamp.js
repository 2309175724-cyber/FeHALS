// 高度着色渐变（蓝→青→绿→黄→红）
// 3D 点云着色（useThreeScene）与统计直方图（PointCloudPanel）共用
export function heightColor(t) {
  const stops = [[0,0,1],[0,1,1],[0,1,0],[1,1,0],[1,0,0]]
  const x = Math.max(0, Math.min(1, t)) * (stops.length - 1)
  const i = Math.min(Math.floor(x), stops.length - 2)
  const f = x - i
  const a = stops[i], b = stops[i + 1]
  return [a[0]+(b[0]-a[0])*f, a[1]+(b[1]-a[1])*f, a[2]+(b[2]-a[2])*f]
}

export function heightCssColor(t) {
  const [r, g, b] = heightColor(t)
  return `rgb(${Math.round(r * 255)}, ${Math.round(g * 255)}, ${Math.round(b * 255)})`
}
