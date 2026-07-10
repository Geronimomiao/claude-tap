# 待补生成的素材（Codex 额度恢复后）

已有：`hero-bg.png`（hero 山景）、`mist-bg.png`（雾山浅色背景）。
以下 6 张生成后放进本目录、文件名对上即可，页面会自动用真图替换占位裁切（无需改代码）。

**调用模板**（务必串行，一次只跑一个 `codex exec`，并发会死锁）：

```bash
OUT=/Users/simiao/Desktop/claude-ai/altai-page/images
codex exec --full-auto --skip-git-repo-check -C "$OUT" \
  -c sandbox_workspace_write.network_access=true \
  "重要：请使用 Codex 内置的 image_gen 工具生成（不要走 CLI 回退）。请用 \$imagegen 生成…（下方对应提示词），保存到 ./<文件名>，最后打印 Saved: <绝对路径>"
```

## person.png — 竖版 1024x1536，背景透明（background=transparent, alpha PNG）
Transparent cutout of a hiker for a layered hero collage. Subject: a young woman seen from behind (back view, head turned very slightly to the right), short coppery auburn hair tucked under an olive-green ribbed knit beanie, oversized dark forest-green chunky knit sweater with high rolled collar, large tan-brown canvas-and-leather backpack on both shoulders, arms relaxed, framed head to mid-thigh. Soft overcast daylight, subtle rim light. Photorealistic. Fully transparent background, crisp cutout edges, no scenery, no text, no watermark.

## card-ring.png — 横版 1536x1024（ПО КОЛЬЦУ АЛТАЯ）
Deep green river canyon valley in the Altai mountains, steep grassy canyon walls, a dirt road and river winding along the flat valley floor, tiny tourist camp with small blue-roofed cabins far below, overcast soft light, view from the canyon rim, photorealistic. No text, no watermark.

## card-glacier.png — 横版 1536x1024（К ЛЕДНИКАМ АКТРУ）
Aktru glacier alpine valley: snow-covered rocky peaks, grey stone moraine, a small milky-turquoise glacial lake, patches of snow, two tiny red expedition tents on a distant snowfield, cold grey-blue-white palette, photorealistic mountaineering photography. No text, no watermark.

## card-spring.png — 横版 1536x1024（ВЕСЕННИЙ ТУР）
Spring sunset in the Altai mountains: low golden sun flaring over layered dark ridges, foreground hillside covered in blooming purple-pink maralnik rhododendron bushes, warm golden haze, dramatic photorealistic landscape. No text, no watermark.

## card-glamping.png — 横版 1536x1024（ГЛЭМПИНГ ТУР）
Modern minimalist black metal glamping cabin with a flat roof and one large panoramic window glowing warm, among tall pine trees, a woman in a long white dress on the small wooden deck by the open door, late afternoon forest light, cozy editorial travel photography. No text, no watermark.

## card-lakes.png — 横版 1536x1024（СИЯНИЕ ОЗЕР）
A small unreal-turquoise geyser lake in the Altai mountains: vivid azure-cyan water with concentric pale silt rings on the bottom, ringed by golden-orange autumn larch trees and dark pines, saturated vibrant colors, slight elevated angle, photorealistic. No people, no text, no watermark.
