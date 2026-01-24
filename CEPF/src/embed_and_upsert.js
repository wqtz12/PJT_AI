
require('dotenv').config();
const fs = require('fs');
const path = require('path');
const { embedText } = require('./utils/embed');
const { initIndex, upsertVectors } = require('./utils/vectorStore');
const { parseFile } = require('./utils/textParser');

const BATCH_SIZE = 100; // Adjust batch size as needed

/**
 * Chunks text into smaller pieces.
 * @param {string} text - The text to chunk.
 * @param {number} chunkSize - The size of each chunk.
 * @param {number} chunkOverlap - The overlap between chunks.
 * @returns {Array<string>} - An array of text chunks.
 */
function chunkText(text, chunkSize = 1000, chunkOverlap = 200) {
  const chunks = [];
  let i = 0;
  while (i < text.length) {
    chunks.push(text.slice(i, i + chunkSize));
    i += chunkSize - chunkOverlap;
  }
  return chunks;
}

/**
 * Processes a file, creates embeddings, and upserts them to the vector store.
 * @param {string} filePath - The path to the file.
 * @param {string} indexName - The name of the index.
 */
async function embedAndUpsert(filePath, indexName) {
  console.log(`Processing file: ${filePath}`);

  const text = await parseFile(filePath);
  const chunks = chunkText(text);

  console.log(`Creating ${chunks.length} embeddings...`);

  const index = await initIndex(indexName);

  for (let i = 0; i < chunks.length; i += BATCH_SIZE) {
    const batch = chunks.slice(i, i + BATCH_SIZE);
    const embeddings = await Promise.all(batch.map(embedText));

    const vectors = embeddings.map((embedding, j) => {
      const originalId = `${path.basename(filePath)}-${i + j}`;
      return {
        id: Buffer.from(originalId).toString('base64'),
        values: embedding,
        metadata: { text: batch[j] },
      };
    });

    console.log(`Upserting batch ${i / BATCH_SIZE + 1}...`);
    await upsertVectors(index, vectors);
  }

  console.log('Done!');
}

// --- Main Execution ---
if (require.main === module) {
  const filePath = process.argv[2];
  const indexName = process.env.INDEX_NAME || 'experiences';

  if (!filePath) {
    console.error('Please provide a file path as an argument.');
    process.exit(1);
  }

  embedAndUpsert(filePath, indexName).catch(console.error);
}

module.exports = {
  embedAndUpsert,
};
