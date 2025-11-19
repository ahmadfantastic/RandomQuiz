import pdfMake from 'pdfmake/build/pdfmake';
import pdfFonts from 'pdfmake/build/vfs_fonts';
import DOMPurify from 'dompurify';
import htmlToPdfmake from 'html-to-pdfmake';
import { marked } from 'marked';

pdfMake.vfs = pdfFonts;

const toPlainText = (value = '') =>
  String(value || '')
    .replace(/<[^>]+>/g, '')
    .replace(/\s+/g, ' ')
    .trim();

const convertMarkdownToPdfContent = (markdown = '') => {
  const trimmed = (markdown || '').trim();
  if (!trimmed) {
    return [];
  }
  const dirtyHtml = marked(trimmed, { breaks: true });
  const cleanHtml = DOMPurify.sanitize(dirtyHtml);
  const pdfContent = htmlToPdfmake(cleanHtml, { defaultStyles: false });
  return Array.isArray(pdfContent) ? pdfContent : [pdfContent];
};

const buildDocDefinition = ({
  printableFilename,
  quiz,
  details,
  printableSlots,
  ratingCriteria,
  ratingScaleOptions,
}) => {
  const descriptionContent = convertMarkdownToPdfContent(details?.description || '');
  const identityContent = convertMarkdownToPdfContent(
    details?.identity_instruction || 'Required so your instructor can match your submission.'
  );
  const docContent = [];
  docContent.push({ text: quiz?.title || 'Quiz', style: 'printTitle' });
  docContent.push(...descriptionContent);
  docContent.push(...identityContent);
  docContent.push({
    text: 'Student identifier',
    style: 'sectionLabel',
    margin: [0, 6, 0, 4],
  });
  docContent.push({
    canvas: [
      {
        type: 'rect',
        x: 0,
        y: 0,
        w: 520,
        h: 40,
        r: 6,
        lineWidth: 0.6,
      },
    ],
    margin: [0, 0, 0, 6],
  });
  docContent.push({
    text: 'Write the identifier used for this quiz.',
    style: 'noteText',
    margin: [0, 0, 0, 12],
  });

  printableSlots.forEach(({ slot, problem, index }) => {
    const displayLabel = slot?.label || 'Untitled Slot';
    const slotTitle = `${slot.order || index + 1}: ${displayLabel}`;
    docContent.push({ text: slotTitle, style: 'slotTitle', margin: [0, 10, 0, 4] });
    docContent.push({
      text: toPlainText(slot.instruction),
      style: 'printBody',
      margin: [0, 0, 0, 6],
    });
    docContent.push({
      text: problem.display_label,
      style: 'slotProblemLabel',
      margin: [0, 0, 0, 2],
    });
    docContent.push({
      text: toPlainText(problem.problem_statement),
      style: 'printBody',
      margin: [0, 0, 0, 6],
    });
    const isRating = slot.response_type === 'rating';
    if (!isRating) {
      docContent.push({
        canvas: [
          {
            type: 'rect',
            x: 0,
            y: 0,
            w: 520,
            h: 120,
            r: 6,
            lineWidth: 0.6,
          },
        ],
        margin: [0, 6, 0, 10],
      });
    }
    if (isRating) {
      const headerCells = [
        { text: 'Description', style: 'tableHeader' },
        ...ratingScaleOptions.map((scale) => ({
          text: scale.label || String(scale.value),
          style: 'tableHeader',
          alignment: 'center',
        })),
      ];
      const tableBody = [
        headerCells,
        ...ratingCriteria.map((criterion) => [
          {
            text: `${toPlainText(
              criterion?.description || ''
            )}`.trim(),
            style: 'tableCell',
          },
          ...ratingScaleOptions.map(() => ({
            text: 'o',
            style: 'tableCell',
            alignment: 'center',
            fontSize: 20,
          })),
        ]),
      ];
      const scaleColumnWidth = `${50 / ratingScaleOptions.length}%`;
      docContent.push({
        table: {
          headerRows: 1,
          widths: ['50%', ...ratingScaleOptions.map(() => scaleColumnWidth)],
          body: tableBody,
        },
        layout: 'lightHorizontalLines',
        margin: [0, 0, 0, 10],
      });
    }
  });

  return {
    pageSize: 'A4',
    pageMargins: [36, 36, 36, 36],
    content: docContent,
    styles: {
      printTitle: { fontSize: 16, bold: true },
      slotTitle: { fontSize: 12, bold: true },
      slotProblemLabel: { fontSize: 12, bold: true },
      sectionLabel: { fontSize: 10, color: '#444444', bold: true, characterSpacing: 0.5 },
      printBody: { fontSize: 10, margin: [0, 0, 0, 4] },
      noteText: { fontSize: 9, color: '#555555' },
      tableHeader: { fontSize: 9, bold: true, fillColor: '#f5f5f5' },
      tableCell: { fontSize: 10 },
      markdownHeading1: { fontSize: 12, bold: true, margin: [0, 8, 0, 4] },
      markdownHeading2: { fontSize: 11, bold: true, margin: [0, 6, 0, 4] },
      markdownHeading3: { fontSize: 11, bold: true, margin: [0, 6, 0, 4] },
      markdownHeading4: { fontSize: 11, bold: true, margin: [0, 6, 0, 4] },
      markdownHeading5: { fontSize: 10, bold: true, margin: [0, 6, 0, 4] },
      markdownHeading6: { fontSize: 10, bold: true, margin: [0, 6, 0, 4] },
      markdownParagraph: { fontSize: 10, margin: [0, 0, 0, 6] },
      markdownListItem: { fontSize: 10, margin: [0, 0, 0, 2] },
      markdownCode: {
        fontSize: 9,
        font: 'Courier',
        fillColor: '#f3f4f6',
        margin: [0, 4, 0, 6],
        color: '#0f172a',
      },
      markdownBlockquote: {
        italics: true,
        color: '#475569',
        margin: [8, 2, 0, 6],
      },
    },
    defaultStyle: {
      fontSize: 10,
      lineHeight: 1.2,
    },
  };
};

export const previewQuizPdf = ({
  printableFilename,
  quiz,
  details,
  printableSlots,
  ratingCriteria,
  ratingScaleOptions,
}) =>
  new Promise((resolve, reject) => {
    try {
      const definition = buildDocDefinition({
        printableFilename,
        quiz,
        details,
        printableSlots,
        ratingCriteria,
        ratingScaleOptions,
      });
      pdfMake.createPdf(definition).print();
      resolve();
    } catch (error) {
      reject(error);
    }
  });
