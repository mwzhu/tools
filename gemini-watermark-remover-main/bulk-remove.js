#!/usr/bin/env node
/**
 * Bulk watermark remover CLI for Gemini images
 * Usage: node bulk-remove.js [input-folder] [output-folder]
 */

import { createCanvas, loadImage } from 'canvas';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Constants
const ALPHA_THRESHOLD = 0.002;
const MAX_ALPHA = 0.99;
const LOGO_VALUE = 255;

// Calculate alpha map from background image
function calculateAlphaMap(imageData) {
    const { width, height, data } = imageData;
    const alphaMap = new Float32Array(width * height);

    for (let i = 0; i < alphaMap.length; i++) {
        const idx = i * 4;
        const r = data[idx];
        const g = data[idx + 1];
        const b = data[idx + 2];
        const maxChannel = Math.max(r, g, b);
        alphaMap[i] = maxChannel / 255.0;
    }

    return alphaMap;
}

// Detect watermark config based on image dimensions
function detectWatermarkConfig(imageWidth, imageHeight) {
    if (imageWidth > 1024 && imageHeight > 1024) {
        return { logoSize: 96, marginRight: 64, marginBottom: 64 };
    } else {
        return { logoSize: 48, marginRight: 32, marginBottom: 32 };
    }
}

// Calculate watermark position
function calculateWatermarkPosition(imageWidth, imageHeight, config) {
    const { logoSize, marginRight, marginBottom } = config;
    return {
        x: imageWidth - marginRight - logoSize,
        y: imageHeight - marginBottom - logoSize,
        width: logoSize,
        height: logoSize
    };
}

// Remove watermark using reverse alpha blending
function removeWatermark(imageData, alphaMap, position) {
    const { x, y, width, height } = position;

    for (let row = 0; row < height; row++) {
        for (let col = 0; col < width; col++) {
            const imgIdx = ((y + row) * imageData.width + (x + col)) * 4;
            const alphaIdx = row * width + col;

            let alpha = alphaMap[alphaIdx];

            if (alpha < ALPHA_THRESHOLD) {
                continue;
            }

            alpha = Math.min(alpha, MAX_ALPHA);
            const oneMinusAlpha = 1.0 - alpha;

            for (let c = 0; c < 3; c++) {
                const watermarked = imageData.data[imgIdx + c];
                const original = (watermarked - alpha * LOGO_VALUE) / oneMinusAlpha;
                imageData.data[imgIdx + c] = Math.max(0, Math.min(255, Math.round(original)));
            }
        }
    }
}

// Load alpha maps
async function loadAlphaMaps() {
    const bg48Path = path.join(__dirname, 'src/assets/bg_48.png');
    const bg96Path = path.join(__dirname, 'src/assets/bg_96.png');

    const bg48 = await loadImage(bg48Path);
    const bg96 = await loadImage(bg96Path);

    const canvas48 = createCanvas(48, 48);
    const ctx48 = canvas48.getContext('2d');
    ctx48.drawImage(bg48, 0, 0);
    const alphaMap48 = calculateAlphaMap(ctx48.getImageData(0, 0, 48, 48));

    const canvas96 = createCanvas(96, 96);
    const ctx96 = canvas96.getContext('2d');
    ctx96.drawImage(bg96, 0, 0);
    const alphaMap96 = calculateAlphaMap(ctx96.getImageData(0, 0, 96, 96));

    return { 48: alphaMap48, 96: alphaMap96 };
}

// Process a single image
async function processImage(inputPath, outputPath, alphaMaps) {
    const image = await loadImage(inputPath);

    const canvas = createCanvas(image.width, image.height);
    const ctx = canvas.getContext('2d');
    ctx.drawImage(image, 0, 0);

    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const config = detectWatermarkConfig(canvas.width, canvas.height);
    const position = calculateWatermarkPosition(canvas.width, canvas.height, config);
    const alphaMap = alphaMaps[config.logoSize];

    removeWatermark(imageData, alphaMap, position);
    ctx.putImageData(imageData, 0, 0);

    // Save as PNG
    const buffer = canvas.toBuffer('image/png');
    fs.writeFileSync(outputPath, buffer);
}

// Main function
async function main() {
    const args = process.argv.slice(2);
    const inputFolder = args[0] || path.join(__dirname, 'images');
    const outputFolder = args[1] || path.join(__dirname, 'output');

    // Create output folder if it doesn't exist
    if (!fs.existsSync(outputFolder)) {
        fs.mkdirSync(outputFolder, { recursive: true });
    }

    console.log(`Input folder: ${inputFolder}`);
    console.log(`Output folder: ${outputFolder}`);
    console.log('');

    // Load alpha maps
    console.log('Loading alpha maps...');
    const alphaMaps = await loadAlphaMaps();

    // Get all image files
    const imageExtensions = ['.png', '.jpg', '.jpeg', '.webp'];
    const files = fs.readdirSync(inputFolder).filter(file => {
        const ext = path.extname(file).toLowerCase();
        return imageExtensions.includes(ext);
    });

    if (files.length === 0) {
        console.log('No image files found in input folder.');
        return;
    }

    console.log(`Found ${files.length} image(s) to process.\n`);

    // Process each image
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const inputPath = path.join(inputFolder, file);
        const outputName = `unwatermarked_${file.replace(/\.[^.]+$/, '.png')}`;
        const outputPath = path.join(outputFolder, outputName);

        try {
            console.log(`[${i + 1}/${files.length}] Processing: ${file}`);
            await processImage(inputPath, outputPath, alphaMaps);
            console.log(`    Saved: ${outputName}`);
        } catch (error) {
            console.error(`    Error: ${error.message}`);
        }
    }

    console.log('\nDone!');
}

main().catch(console.error);
