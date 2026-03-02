const path = require('path');
require('dotenv').config({ path: path.resolve(__dirname, '../.env') });
const fs = require('fs');
const { parseFile } = require('../src/utils/textParser');
const { addDocument } = require('../src/utils/firebase');

const DOCS_DIR = path.join(__dirname, '..', 'docs');
const FIRESTORE_COLLECTION = 'experiences';

/**
 * 지정된 파일을 파싱하여 Firestore에 저장합니다.
 * @param {string} file - 처리할 파일의 이름
 */
async function processFile(file) {
  const resolvedDocsDir = path.resolve(DOCS_DIR);
  const requestedPath = path.resolve(DOCS_DIR, file);

  if (!requestedPath.startsWith(resolvedDocsDir)) {
    console.error(`[오류] 허용되지 않은 파일 경로입니다: ${file}`);
    return;
  }

  const filePath = requestedPath;
  console.log('[시작] 파일 처리 중: %s', file);

  try {
    // 파일 존재 여부 확인
    if (!fs.existsSync(filePath)) {
      console.error('[오류] \'%s\' 디렉토리에서 파일을 찾을 수 없습니다: %s', DOCS_DIR, file);
      return;
    }

    // 1. 파일 내용 파싱
    const content = await parseFile(filePath);
    if (!content || content.trim() === '') {
      console.log('[경고] 내용이 비어있어 파일을 건너뜁니다: %s', file);
      return;
    }

    // 2. Firestore에 저장할 데이터 객체 생성
    const dataToSave = {
      source: file,
      content: content,
      type: 'document', // 타입 지정
    };

    // 3. Firestore에 문서 추가
    await addDocument(FIRESTORE_COLLECTION, dataToSave);
    console.log('[완료] %s -> Firestore 저장 완료', file);

  } catch (error) {
    console.error('[오류] 파일 처리 중 오류 발생: %s', file, error);
  }
}

/**
 * docs 폴더의 파일들을 Firestore에 가져오는 메인 함수
 */
async function importDocsToFirestore() {
  const targetFile = process.argv[2]; // 커맨드 라인에서 파일명 인자 받기

  if (targetFile) {
    // 특정 파일이 인자로 주어진 경우, 해당 파일만 처리
    console.log('\'%s\' 디렉토리에서 특정 파일 가져오기를 시작합니다: %s', DOCS_DIR, targetFile);
    await processFile(targetFile);
  } else {
    // 인자가 없는 경우, 기존 로직대로 모든 파일을 처리
    console.log('\'%s\' 디렉토리의 모든 파일 가져오기를 시작합니다...', DOCS_DIR);
    try {
      const files = fs.readdirSync(DOCS_DIR);
      if (files.length === 0) {
        console.log('docs 폴더에 처리할 파일이 없습니다.');
        return;
      }

      console.log('총 %d개의 파일을 처리합니다.', files.length);
      for (const file of files) {
        await processFile(file); // 개별 파일 처리 함수 호출
      }
    } catch (error) {
      console.error('\'%s\' 디렉토리를 읽는 중 오류가 발생했습니다.', DOCS_DIR, error);
    }
  }

  console.log('파일 가져오기 작업을 종료합니다.');
}

// 스크립트 실행
importDocsToFirestore();