const admin = require('firebase-admin');

// .env 파일에서 서비스 계정 키(JSON 문자열)를 로드합니다.
const serviceAccountString = process.env.FIREBASE_SERVICE_ACCOUNT;

if (!serviceAccountString) {
  throw new Error('FIREBASE_SERVICE_ACCOUNT 환경 변수가 설정되지 않았습니다. .env 파일을 확인하세요.');
}

try {
  const serviceAccount = JSON.parse(serviceAccountString);

  admin.initializeApp({
    credential: admin.credential.cert(serviceAccount),
    databaseURL: "https://fir-101-e0467-default-rtdb.firebaseio.com" // Realtime Database URL 추가
  });

  console.log('Firebase Admin SDK가 성공적으로 초기화되었습니다.');

} catch (error) {
  console.error('FIREBASE_SERVICE_ACCOUNT JSON 파싱 중 오류가 발생했습니다.', error);
  throw new Error('서비스 계정 키가 유효한 JSON 형식이 아닙니다.');
}

// Firestore 대신 Realtime Database를 사용합니다.
const db = admin.database();

/**
 * Realtime Database의 특정 경로에 데이터를 추가합니다.
 * @param {string} path - 데이터를 추가할 경로 (Firestore의 'collection'과 유사)
 * @param {object} data - 저장할 데이터 객체
 * @returns {Promise<string>} - 새로 생성된 데이터의 키(ID)
 */
async function addDocument(path, data) {
  try {
    const newDocRef = db.ref(path).push(); // 새 데이터에 대한 참조 생성 및 push
    await newDocRef.set({
      ...data,
      createdAt: admin.database.ServerValue.TIMESTAMP, // Realtime Database용 타임스탬프
    });
    console.log(`'${path}' 경로에 새 데이터가 추가되었습니다 (ID: ${newDocRef.key})`);
    return newDocRef.key;
  } catch (error) {
    console.error(`Realtime Database 데이터 추가 중 오류 발생 (경로: ${path}):`, error);
    throw error;
  }
}

module.exports = {
  db,
  addDocument,
};