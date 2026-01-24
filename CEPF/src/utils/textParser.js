const pdf = require('pdf-parse');
const { TesseractWorker } = require('tesseract.js');
const fs = require('fs');
const path = require('path');
const stringSimilarity = require('string-similarity');
const { parseISO, compareAsc } = require('date-fns');
const mammoth = require('mammoth');

/**
 * Parses text from a file.
 * @param {string} filePath - The path to the file.
 * @returns {Promise<string>} - The extracted text.
 */
async function parseFile(filePath) {
  const fileExtension = path.extname(filePath).toLowerCase();
  
  if (fileExtension === '.pages') {
    console.log(`[경고] .pages 파일 형식은 지원되지 않습니다. 파일을 건너뜁니다: ${path.basename(filePath)}`);
    return '';
  }

  const fileBuffer = fs.readFileSync(filePath);

  switch (fileExtension) {
    case '.pdf':
      return parsePdf(fileBuffer);
    case '.png':
    case '.jpg':
    case '.jpeg':
    case '.bmp':
      return parseImage(fileBuffer);
    case '.txt':
    case '.md':
      return fileBuffer.toString('utf-8');
    case '.docx':
      return parseDocx(fileBuffer);
    default:
      throw new Error(`Unsupported file type: ${fileExtension}`);
  }
}

/**
 * Parses text from a PDF buffer.
 * @param {Buffer} pdfBuffer - The PDF file buffer.
 * @returns {Promise<string>} - The extracted text.
 */
async function parsePdf(pdfBuffer) {
  try {
    const data = await pdf(pdfBuffer);
    return data.text;
  } catch (error) {
    console.error('PDF 파싱 중 오류 발생:', error);
    return '';
  }
}

/**
 * Parses text from an image buffer using OCR.
 * @param {Buffer} imageBuffer - The image file buffer.
 * @returns {Promise<string>} - The extracted text.
 */
async function parseImage(imageBuffer) {
  const worker = new TesseractWorker();
  const { data: { text } } = await worker.recognize(imageBuffer);
  await worker.terminate();
  return text;
}

/**
 * Parses text from a .docx buffer.
 * @param {Buffer} docxBuffer - The .docx file buffer.
 * @returns {Promise<string>} - The extracted text.
 */
async function parseDocx(docxBuffer) {
  const { value } = await mammoth.extractRawText({ buffer: docxBuffer });
  return value;
}

/**
 * Removes duplicate texts from an array based on similarity.
 * @param {string[]} texts - An array of texts.
 * @param {number} [similarityThreshold=0.9] - The similarity threshold.
 * @returns {string[]} - An array of unique texts.
 */
function removeDuplicates(texts, similarityThreshold = 0.9) {
  const uniqueTexts = [];
  for (const text of texts) {
    let isDuplicate = false;
    for (const uniqueText of uniqueTexts) {
      if (stringSimilarity.compareTwoStrings(text, uniqueText) > similarityThreshold) {
        isDuplicate = true;
        break;
      }
    }
    if (!isDuplicate) {
      uniqueTexts.push(text);
    }
  }
  return uniqueTexts;
}

/**
 * Sorts an array of objects with a date property.
 * @param {Array<object>} items - An array of objects, each with a 'date' property in ISO 8601 format.
 * @returns {Array<object>} - The sorted array of objects.
 */
function sortByDate(items) {
  return items.sort((a, b) => compareAsc(parseISO(a.date), parseISO(b.date)));
}

module.exports = {
  parseFile,
  removeDuplicates,
  sortByDate,
};
