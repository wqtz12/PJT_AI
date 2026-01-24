/**
 * Generates a concise summary of a project description.
 * In a real application, this function would use a summarization model like BART or T5.
 * @param {string} projectDescription - The full description of the project.
 * @returns {Promise<string>} - A promise that resolves to the summarized project description.
 */
async function generateSummary(projectDescription) {
  console.log('Generating summary for project...');

  // Replace this with a call to your summarization model.
  // For example, using a Hugging Face Transformers pipeline:
  // const summarizer = await pipeline('summarization', 'facebook/bart-large-cnn');
  // const summary = await summarizer(projectDescription, { max_length: 100 });
  // return summary[0].summary_text;

  const summary = `This is a summary of the project: ${projectDescription.substring(0, 100)}...`;
  return Promise.resolve(summary);
}

/**
 * Creates a JSON object with project metadata.
 * @param {string} projectName - The name of the project.
 * @param {string} duration - The project duration (e.g., "2022.03 ~ 2023.02").
 * @param {string} role - The user's role in the project.
 * @param {Array<string>} techStack - The technologies used in the project.
 * @param {string} summary - The project summary.
 * @param {Array<string>} tags - Metadata tags (e.g., technology stack, industry, complexity).
 * @returns {object} - The project metadata as a JSON object.
 */
function createProjectMetadata(projectName, duration, role, techStack, summary, tags) {
  return {
    project_name: projectName,
    duration: duration,
    role: role,
    tech_stack: techStack,
    summary: summary,
    tags: tags,
  };
}

module.exports = {
  generateSummary,
  createProjectMetadata,
};
