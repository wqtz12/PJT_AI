require('dotenv').config();

// The dimension for the all-MiniLM-L6-v2 model
const EMBEDDING_DIMENSION = 384;

let extractorPromise;

async function getExtractor() {
  if (!extractorPromise) {
    extractorPromise = new Promise(async (resolve, reject) => {
      try {
        const { pipeline } = await import('@xenova/transformers');
        const extractor = await pipeline('feature-extraction', 'Xenova/all-MiniLM-L6-v2');
        resolve(extractor);
      } catch (error) {
        reject(error);
      }
    });
  }
  return extractorPromise;
}

/**
 * Creates an embedding for a given text using Hugging Face transformers.
 * @param {string} text - The text to embed.
 * @returns {Promise<Array<number>>} - A promise that resolves to the embedding vector.
 */
async function embedText(text) {
  if (process.env.USE_PLACEHOLDERS === 'true') {
    console.log(`[Placeholder] Embedding text: "${text}"`);
    const dummyVector = Array(EMBEDDING_DIMENSION).fill(0);
    dummyVector[0] = 1;
    return dummyVector;
  }

  // --- Hugging Face Model ---
  const extractor = await getExtractor();
  const result = await extractor(text, { pooling: 'mean', normalize: true });
  return Array.from(result.data);
}

module.exports = {
  embedText,
};
