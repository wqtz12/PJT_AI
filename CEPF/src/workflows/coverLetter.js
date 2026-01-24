const { retrieve, generate } = require('../lib/rag');

/**
 * Drafts a cover letter section based on the STAR method.
 * @param {object} experience - The experience to highlight.
 * @param {object} companyProfile - The company's profile.
 * @param {string} role - The target role.
 * @param {string} topic - The specific topic for the cover letter.
 * @param {number} characterLimit - The character limit for the response.
 * @returns {Promise<string>} - A promise that resolves to the drafted section.
 */
async function draftCoverLetterSection(experience, companyProfile, role, topic, characterLimit) {
  const prompt = `
  As a professional technical career consultant, write a cover letter section in KOREAN for the "${role}" position at "${companyProfile.name}".
  The section should address the following topic: "${topic}".
  Use the provided project experience to demonstrate the candidate's competence.
  Strictly follow the STAR structure (Situation, Task, Action, Result) and the specified style guidelines.
  The response should be concise and adhere to a character limit of approximately ${characterLimit} characters.

  **Style Guidelines:**
  - **Tone:** Professional and dry. Focus on competence and solutions, not passion.
  - **Structure:** Start with a headline, then Situation (10%), Task (10%), Action (50%), and Result (30%).
  - **Content:** Be deductive. Start with the conclusion (headline). Quantify results whenever possible.

  **Project Experience:**
  ---
  ${experience}
  ---

  **Company Keywords to Align With:**
  - Values: ${companyProfile.values.join(', ')}
  - Skills for ${role}: ${companyProfile.required_skills.join(', ')}

  Generate the response now.
  `;

  return generate(prompt);
}


/**
 * Generates a company-specific cover letter.
 * @param {string} companyName - The name of the company.
 * @param {Array<string>} companyValues - Pre-analyzed company values.
 * @param {Array<string>} requiredSkills - Pre-analyzed required skills for the role.
 * @param {string} companyMission - Pre-analyzed company mission.
 * @param {string} role - The target role.
 * @param {string} topic - The specific topic for the cover letter.
 * @param {number} characterLimit - The character limit for the response.
 * @returns {Promise<string>} - A promise that resolves to the generated cover letter.
 */
async function generateCoverLetterWorkflow(companyName, companyValues, requiredSkills, companyMission, role, topic, characterLimit) {
  // 1. Create company profile from pre-analyzed data
  const companyProfile = {
    name: companyName,
    values: companyValues,
    required_skills: requiredSkills,
    mission: companyMission
  };

  // 2. Episode Selection (Phase 1 & 2 from GEMINI.md)
  // Identify core competencies and find the single most relevant project.
  const query = `A project that demonstrates skills like ${companyProfile.required_skills.join(', ')} and aligns with values such as ${companyProfile.values.join(', ')}.`;
  const relevantExperiences = await retrieve(query, 1); // Retrieve the single most relevant experience

  if (!relevantExperiences || relevantExperiences.length === 0) {
    return "Could not find a relevant experience to write the cover letter.";
  }
  const selectedExperience = relevantExperiences[0];

  // 3. Drafting (Phase 3 from GEMINI.md)
  // Generate the cover letter section using the STAR method.
  const finalCoverLetter = await draftCoverLetterSection(selectedExperience, companyProfile, role, topic, characterLimit);

  return finalCoverLetter;
}

module.exports = {
  generateCoverLetterWorkflow,
};