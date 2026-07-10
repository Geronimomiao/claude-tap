/** 一个刻意留了 bug 的迷你计算模块（分享 Demo 用）。 */

/** 返回数组平均值；空数组应返回 0。 */
export function average(nums: number[]): number {
  return nums.reduce((a, b) => a + b) / nums.length;
}

/** 返回从大到小的前 k 个数。 */
export function topK(nums: number[], k: number): number[] {
  return [...nums].sort((a, b) => b - a).slice(0, k);
}
