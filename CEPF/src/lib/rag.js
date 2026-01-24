const { queryVectors, initIndex } = require('../utils/vectorStore');
const { embedText } = require('../utils/embed');

require('dotenv').config();

async function getQueryEmbedding(query) {
  console.log(`Embedding query: "${query}"`);
  return await embedText(query);
}
 
/**
 * Retrieves relevant documents from the vector store.
 * @param {string} query - The user's query.
 * @param {number} topK - The number of documents to retrieve.
 * @returns {Promise<Array<object>>} - A promise that resolves to an array of retrieved documents.
 */
async function retrieve(query, topK) {
  const indexName = 'experiences'; // Or get it from config
  const index = await initIndex(indexName);

  const queryEmbedding = await getQueryEmbedding(query);

  const results = await queryVectors(index, queryEmbedding, topK);
  return results.matches.map(match => match.metadata.text);
}

let generatorPromise;

async function _initGenerator() {
  const { pipeline } = await import('@xenova/transformers');
  return pipeline('text-generation', 'Xenova/distilgpt2');
}

async function getGenerator() {
  if (!generatorPromise) {
    generatorPromise = _initGenerator();
  }
  return generatorPromise;
}

function getPlaceholderResponse(prompt) {
  console.log('[Placeholder] Generating response...');
  if (prompt.includes("STAR")) {
      return `[Placeholder STAR-based Response]\n### 헤드라인: 문제 해결 능력으로 40% 레이턴시 감소\n\n**Situation:** 사용자가 몰리는 특정 기능에서 심각한 성능 저하가 발생했습니다.\n**Task:** 원인을 분석하고 성능을 개선하는 임무를 맡았습니다.\n**Action:** 프로파일링을 통해 데이터베이스 쿼리가 병목 현상의 원인임을 발견했습니다. 복잡한 조인을 최적화하고, 쿼리 캐싱 전략을 도입했으며, N+1 문제를 해결하기 위해 데이터 로딩 로직을 리팩토링했습니다.\n**Result:** 이 최적화를 통해 해당 기능의 평균 응답 시간을 40% 단축하고, 서버 부하를 25% 감소시키는 정량적 성과를 달성했습니다.`;
  }
  if (prompt.includes("cover letter")) {
      return `[Placeholder Cover Letter]\n${prompt.split("Experiences:")[1] || '경험을 바탕으로'}' 회사 가치와 부합하는 자기소개서를 작성했습니다.`;
  }
  return `[Placeholder LLM Response]\nBased on the prompt, I am generating a response.`;
}


/**
 * Generates a response based on a given prompt.
 * Uses a placeholder if USE_PLACEHOLDERS is true, otherwise calls the Hugging Face API.
 * @param {string} prompt - The full prompt to send to the LLM.
 * @returns {Promise<string>} - A promise that resolves to the generated response.
 */
async function generate(prompt) {
  console.log('---PROMPT---');
  console.log(prompt);
  console.log('------------');

  if (process.env.USE_PLACEHOLDERS === 'true') {
    return getPlaceholderResponse(prompt);
  }

  // --- Hugging Face Generation ---
  const generator = await getGenerator();
  const result = await generator(prompt, { max_new_tokens: 200 });
  const generatedText = result[0].generated_text;

  console.log('---LLM RESPONSE---');
  console.log(generatedText);
  console.log('------------------');
  return generatedText;
}


/**
 * The main RAG pipeline.
 * @param {string} query - The user's query.
 * @param {number} [topK=3] - The number of documents to retrieve.
 * @returns {Promise<string>} - A promise that resolves to the final generated answer.
 */
async function rag(query, topK = 3) {
  const documents = await retrieve(query, topK);
  const prompt = `Query: ${query}\n\nDocuments:\n${documents.join('\n\n')}\n\nAnswer:`;
  const answer = await generate(prompt);
  return answer;
}

module.exports = {
  rag,
  retrieve,
  generate,
};
