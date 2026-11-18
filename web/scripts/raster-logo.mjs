// Rasterise the logo SVGs with the sharp that Next already ships (spec 22).
// Usage: node scripts/raster-logo.mjs IN.svg OUT.png SIZE
import sharp from "sharp";
const [, , input, output, size] = process.argv;
await sharp(input, { density: 600 }).resize(Number(size), Number(size)).png().toFile(output);
