/**
 * 보안 스캔 보고서 이메일 발송 API
 *
 * Express.js 또는 Next.js API Route로 사용
 *
 * 환경변수:
 *   SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
 */

import nodemailer from 'nodemailer';

// ============================================================
// Express.js 미들웨어
// ============================================================
export async function sendSecurityReportHandler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { to, subject, html, results } = req.body;

  if (!to || !subject) {
    return res.status(400).json({ error: 'Missing required fields: to, subject' });
  }

  try {
    const result = await sendEmail({ to, subject, html, results });
    res.status(200).json({ success: true, messageId: result.messageId });
  } catch (error) {
    console.error('Email error:', error);
    res.status(500).json({ error: error.message });
  }
}

// ============================================================
// 이메일 발송 함수
// ============================================================
export async function sendEmail({ to, subject, html, results }) {
  const transporter = nodemailer.createTransport({
    host: process.env.SMTP_HOST || 'smtp.gmail.com',
    port: parseInt(process.env.SMTP_PORT || '587'),
    secure: process.env.SMTP_SECURE === 'true',
    auth: {
      user: process.env.SMTP_USER,
      pass: process.env.SMTP_PASS,
    },
  });

  const mailOptions = {
    from: process.env.SMTP_FROM || `Security Scanner <${process.env.SMTP_USER}>`,
    to,
    subject,
    html,
    attachments: results ? [
      {
        filename: `security-report-${Date.now()}.json`,
        content: JSON.stringify(results, null, 2),
        contentType: 'application/json',
      },
    ] : [],
  };

  return await transporter.sendMail(mailOptions);
}

// ============================================================
// Next.js API Route (pages/api/send-security-report.js)
// ============================================================
export default async function handler(req, res) {
  return sendSecurityReportHandler(req, res);
}


// ============================================================
// Express.js 라우터 설정 예시
// ============================================================
/*
import express from 'express';
import { sendSecurityReportHandler } from './api/send-security-report.js';

const app = express();
app.use(express.json());

app.post('/api/send-security-report', sendSecurityReportHandler);

app.listen(3001, () => console.log('API server running on port 3001'));
*/
