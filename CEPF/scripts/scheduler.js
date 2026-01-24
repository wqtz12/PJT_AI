
require('dotenv').config({ path: '../.env' });
const fs = require('fs');
const path = require('path');
const { parseFile } = require('../src/utils/textParser');
const { addExperience } = require('../src/utils/dataManager');
const { embedText } = require('../src/utils/embed');
const { initIndex, upsertVectors } = require('../src/utils/vectorStore');

// 처리할 문서와 처리된 문서를 위한 디렉토리 경로
const DOCS_TO_PROCESS_DIR = path.join(__dirname, '..', 'documents_to_process');
const PROCESSED_DOCS_DIR = path.join(__dirname, '..', 'processed_documents');

// 인덱스 이름
const INDEX_NAME = 'career-experiences';

/**
 * 스케줄링 작업을 실행하는 메인 함수
 */
async function runScheduledJob() {
  console.log('스케줄링 작업을 시작합니다...');

  try {
    // Pinecone 인덱스 초기화
    // 인덱스 초기화
    console.log(`인덱스 '${INDEX_NAME}'를 초기화합니다.`);
    const index = await initIndex(INDEX_NAME);

    // 처리할 파일 목록 읽기
    const files = fs.readdirSync(DOCS_TO_PROCESS_DIR);

    if (files.length === 0) {
      console.log('새로 처리할 문서가 없습니다.');
      return;
    }

    console.log(`총 ${files.length}개의 새 문서를 처리합니다.`);

    // 각 파일을 순회하며 처리
    for (const file of files) {
      const filePath = path.join(DOCS_TO_PROCESS_DIR, file);
      console.log(`[시작] 파일 처리 중: ${file}`);

      try {
        // 1. 파일 파싱
        const content = await parseFile(filePath);
        if (!content || content.trim() === '') {
          console.log(`[경고] 내용이 비어있어 파일을 건너뜁니다: ${file}`);
          continue;
        }

        // 2. 데이터베이스에 저장
        // 파일 내용을 기반으로 'work' 또는 'project' 타입을 결정할 수 있습니다.
        // 여기서는 'project'로 기본 설정합니다.
        const experienceType = 'project';
        const newRecord = await addExperience(content, experienceType, file); // 파일명을 키워드로 활용
        console.log(`  - DB에 저장 완료 (ID: ${newRecord.id})`);

        // 3. 텍스트 임베딩
        const embedding = await embedText(content);
        console.log('  - 텍스트 임베딩 완료');

        // 4. 벡터 데이터베이스에 업로드
        const vector = {
          id: newRecord.id.toString(),
          values: embedding,
          metadata: {
            content: content.substring(0, 1000), // 메타데이터 크기 제한을 고려하여 일부만 저장
            type: newRecord.type,
            source: file,
            created_at: newRecord.start_date,
          },
        };
        await upsertVectors(index, [vector]);
        console.log('  - 벡터 DB에 업로드 완료');

        // 5. 처리 완료된 파일 이동
        const newFilePath = path.join(PROCESSED_DOCS_DIR, file);
        fs.renameSync(filePath, newFilePath);
        console.log(`[완료] 파일 이동: ${file} -> ${PROCESSED_DOCS_DIR}`);

      } catch (error) {
        console.error(`[오류] 파일 처리 중 오류 발생: ${file}`, error);
        // 오류가 발생한 파일은 이동하지 않고 다음 파일 처리를 계속합니다.
      }
    }

  } catch (error) {
    console.error('스케줄링 작업 중 심각한 오류가 발생했습니다.', error);
  } finally {
    console.log('스케줄링 작업을 종료합니다.');
  }
}

// 스크립트 실행
runScheduledJob();
