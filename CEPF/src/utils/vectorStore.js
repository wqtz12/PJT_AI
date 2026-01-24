const fs = require('fs');
const path = require('path');
const faiss = require('faiss-node');

const INDEX_PATH = path.join(__dirname, '../../faiss.index');
const METADATA_PATH = path.join(__dirname, '../../metadata.json');
const EMBEDDING_DIMENSION = 384;

let metadata = {};
if (fs.existsSync(METADATA_PATH)) {
  metadata = JSON.parse(fs.readFileSync(METADATA_PATH, 'utf8'));
}

/**
 * Initializes a Faiss index.
 * @param {string} indexName - The name of the index (used to name the file).
 * @returns {Promise<object>} - The Faiss index object.
 */
async function initIndex(indexName) {
  if (fs.existsSync(INDEX_PATH)) {
    console.log('Loading existing Faiss index.');
    return faiss.Index.read(INDEX_PATH);
  } else {
    console.log('Creating new Faiss index.');
    return new faiss.Index(EMBEDDING_DIMENSION);
  }
}

/**
 * Upserts vectors into a Faiss index and saves metadata.
 * @param {object} index - The Faiss index object.
 * @param {Array<object>} vectors - An array of vectors to upsert.
 */
async function upsertVectors(index, vectors) {
  const values = vectors.map(v => v.values);
  if (values.length === 0) {
    return;
  }

  const flatValues = values.flat();

  if (flatValues.length % EMBEDDING_DIMENSION !== 0) {
    throw new Error('Flat values length is not a multiple of the embedding dimension.');
  }

  index.add(flatValues);

  vectors.forEach((vector, i) => {
    const vectorId = index.ntotal() - values.length + i;
    metadata[vectorId] = {
      id: vector.id,
      metadata: vector.metadata,
    };
  });

  await index.write(INDEX_PATH);
  fs.writeFileSync(METADATA_PATH, JSON.stringify(metadata, null, 2));
  console.log(`Upserted ${vectors.length} vectors. Index and metadata saved.`);
}

/**
 * Queries for similar vectors in a Faiss index.
 * @param {object} index - The Faiss index object.
 * @param {Array<number>} vector - The query vector.
 * @param {number} topK - The number of similar vectors to return.
 * @returns {Promise<object>} - The query results.
 */
async function queryVectors(index, vector, topK) {
  if (index.ntotal() === 0) {
    return { matches: [] };
  }

  const result = index.search(vector, topK);

  const matches = result.labels.map((label, i) => {
    if (metadata[label]) {
      return {
        id: metadata[label].id,
        metadata: metadata[label].metadata,
        score: 1 - result.distances[i], // Convert distance to similarity score
      };
    }
    return null;
  }).filter(match => match !== null);

  return { matches };
}

module.exports = {
  initIndex,
  upsertVectors,
  queryVectors,
};