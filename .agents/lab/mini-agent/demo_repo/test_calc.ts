import assert from "node:assert";
import { average, topK } from "./calculator.ts";

assert.strictEqual(average([1, 2, 3]), 2);
assert.strictEqual(average([]), 0, "空数组应返回 0");
assert.deepStrictEqual(topK([3, 1, 2], 2), [3, 2]);
console.log("ALL TESTS PASSED");
