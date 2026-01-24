const fs = require('fs');
const chrono = require('chrono-node');
const { parseFile } = require('./textParser');
const db = require('./db');

/**
 * Extracts date information from a text.
 * @param {string} text - The text to extract the date from.
 * @returns {Date|null} - The extracted date or null if not found.
 */
function extractDate(text) {
  const results = chrono.parse(text);
  return results.length > 0 ? results[0].start.date() : null;
}

/**
 * Adds a new experience to the database.
 * @param {string} input - The raw text or a path to a file.
 * @param {'work'|'project'} type - The type of experience.
 * @param {string|null} keywords - Keywords associated with the experience.
 * @param {object|null} metadata - Metadata associated with the experience.
 * @returns {Promise<object>} - The newly created record.
 */
async function addExperience(input, type, keywords = null, metadata = null) {
  let content;
  if (fs.existsSync(input)) {
    content = await parseFile(input);
  } else {
    content = input;
  }

  const extractedDate = extractDate(content);
  // The JBSGD.md file specifies start_date and end_date. For simplicity, we'll use the extracted date for both.
  const startDate = extractedDate ? extractedDate.toISOString().split('T')[0] : null;
  const endDate = startDate;

  const queryText = 'INSERT INTO experiences(content, type, start_date, end_date, keywords, metadata) VALUES($1, $2, $3, $4, $5, $6) RETURNING *';
  const values = [content, type, startDate, endDate, keywords, metadata ? JSON.stringify(metadata) : null];

  try {
    const res = await db.query(queryText, values);
    console.log('New experience added:', res.rows[0]);
    return res.rows[0];
  } catch (err) {
    console.error('Error adding experience to the database:', err);
    throw err;
  }
}

/**
 * Retrieves all experiences from the database, sorted by start_date.
 * @returns {Promise<Array<object>>} - An array of experiences.
 */
async function getExperiences() {
  const queryText = 'SELECT * FROM experiences ORDER BY start_date ASC';
  try {
    const res = await db.query(queryText);
    return res.rows;
  } catch (err) {
    console.error('Error retrieving experiences:', err);
    throw err;
  }
}

module.exports = {
  addExperience,
  getExperiences,
};
