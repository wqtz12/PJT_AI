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
  const filePath = path.join(DOCS_DIR, file);
  console.log(`[시작] 파일 처리 중: ${file}`);

  try {
    // 파일 존재 여부 확인
    if (!fs.existsSync(filePath)) {
      console.error(`[오류] '${DOCS_DIR}' 디렉토리에서 파일을 찾을 수 없습니다: ${file}`);
      return;
    }

    // 1. 파일 내용 파싱
    const content = await parseFile(filePath);
    if (!content || content.trim() === '') {
      console.log(`[경고] 내용이 비어있어 파일을 건너뜁니다: ${file}`);
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
    console.log(`[완료] ${file} -> Firestore 저장 완료`);

  } catch (error) {
    console.error(`[오류] 파일 처리 중 오류 발생: ${file}`, error);
  }
}

/**
 * docs 폴더의 파일들을 Firestore에 가져오는 메인 함수
 */
async function importDocsToFirestore() {
  const targetFile = process.argv[2]; // 커맨드 라인에서 파일명 인자 받기

  if (targetFile) {
    // 특정 파일이 인자로 주어진 경우, 해당 파일만 처리
    console.log(`'${DOCS_DIR}' 디렉토리에서 특정 파일 가져오기를 시작합니다: ${targetFile}`);
    await processFile(targetFile);
  } else {
    // 인자가 없는 경우, 기존 로직대로 모든 파일을 처리
    console.log(`'${DOCS_DIR}' 디렉토리의 모든 파일 가져오기를 시작합니다...`);
    try {
      const files = fs.readdirSync(DOCS_DIR);
      if (files.length === 0) {
        console.log('docs 폴더에 처리할 파일이 없습니다.');
        return;
      }

      console.log(`총 ${files.length}개의 파일을 처리합니다.`);
      for (const file of files) {
        await processFile(file); // 개별 파일 처리 함수 호출
      }
    } catch (error) {
      console.error(`'${DOCS_DIR}' 디렉토리를 읽는 중 오류가 발생했습니다.`, error);
    }
  }

  console.log('파일 가져오기 작업을 종료합니다.');
}

// 스크립트 실행
importDocsToFirestore();