const google = require('google-it');
const axios = require('axios');
const cheerio = require('cheerio');
const fs = require('fs');
const pdf = require('pdf-parse');
const { generate } = require('../lib/rag.js');

function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); // $& means the whole matched string
}


async function inferRoleFromResume() {
  console.log('\nAttempting to infer job role from resume...');
  try {
    const pdfPath = './docs/경력이력서.pdf';
    if (!fs.existsSync(pdfPath)) {
      console.warn('Resume PDF not found at', pdfPath);
      return '';
    }

    const dataBuffer = fs.readFileSync(pdfPath);
    const data = await pdf(dataBuffer);
    const resumeText = data.text;

    if (!resumeText) {
      return '';
    }

    const prompt = `Based on the following text, what is the most recent or primary job title? Please respond with only the job title, without any other text.\n\n${resumeText}`;
    
    const inferredRole = await generate(prompt);
    
    const cleanedRole = inferredRole.replace(/[\n\r]/g, ' ').replace(/.*:/, '').trim();
    
    console.log(`Inferred Role: ${cleanedRole}`);
    return cleanedRole;

  } catch (error) {
    console.error('Could not infer role from resume:', error);
    return '';
  }
}

async function scrapeCompanyInfo(companyName, role) {
  try {
    const searchRole = role || 'software engineer';
    const searchResults = await google({ query: `${companyName} ${searchRole} 채용`, limit: 3 });
    const officialSiteResults = await google({ query: `${companyName} 공식 사이트`, limit: 2 });

    const urls = searchResults.map(r => r.link).concat(officialSiteResults.map(r => r.link));
    const uniqueUrls = [...new Set(urls)];

    let scrapedText = '';
    for (const url of uniqueUrls) {
      try {
        const { data } = await axios.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' } });
        const $ = cheerio.load(data);
        scrapedText += $('body').text().replace(/\s\s+/g, ' ');
      } catch (error) {
        console.warn(`Could not fetch ${url}: ${error.message}`);
      }
    }

    const extractMatches = (text, regex, limit) => {
      return text.match(regex)?.slice(0, limit).join(', ') || '';
    };

    const mission = extractMatches(scrapedText, /(미션|mission|비전|vision)/gi, 2);
    const values = extractMatches(scrapedText, /(핵심가치|core values|인재상)/gi, 5);
    const sanitizedSearchRole = escapeRegExp(searchRole);
    const skills = extractMatches(scrapedText, new RegExp(`(${sanitizedSearchRole}|직무|job|skills|자격요건)`, "gi"), 5);
    
    return {
      companyMission: mission,
      companyValues: values ? values.split(', ') : [],
      requiredSkills: skills ? skills.split(', ') : [],
    };
  } catch (error) {
    console.error('An error occurred during web scraping:', error);
    return { companyMission: '', companyValues: [], requiredSkills: [] };
  }
}

module.exports = {
    inferRoleFromResume,
    scrapeCompanyInfo,
};
