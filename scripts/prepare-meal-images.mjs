// Mechanical delivery encoding only: no retouching, compositing or cropping.
// Pass the installed sharp module path; this script does not download dependencies.
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

if (process.argv.length !== 3) throw new Error('Usage: node scripts/prepare-meal-images.mjs <sharp-module-path>')
const sharp = createRequire(import.meta.url)(process.argv[2])
const root = fileURLToPath(new URL('../', import.meta.url))
const assets = path.join(root, 'frontend/public/images/meals')
const slugs = ['chicken-teriyaki', 'salmon-potatoes', 'taco-beef', 'creamy-chicken-pasta', 'tofu-satay', 'falafel-bulgur', 'red-thai-chicken', 'turkey-couscous', 'beef-stroganoff', 'mediterranean-salmon-pasta', 'lentil-sweet-potato', 'egg-fried-rice']
for (const slug of slugs) {
  const input = slug === 'chicken-teriyaki'
    ? path.join(root, 'docs/image-samples/chicken-teriyaki-v1.png')
    : path.join(assets, `${slug}-v1.png`)
  const output = path.join(assets, `${slug}-v1.webp`)
  const source = await sharp(input).metadata()
  if (source.width !== 1448 || source.height !== 1086) throw new Error(`Unexpected source dimensions: ${slug}`)
  const info = await sharp(input).resize({ width: 960, withoutEnlargement: true }).webp({ quality: 82, effort: 6 }).toFile(output)
  if (info.width !== 960 || info.height !== 720 || info.size >= 300000) throw new Error(`Invalid delivery asset: ${slug}`)
  console.log(`${slug}: ${info.width}x${info.height}, ${info.size} bytes`)
}
