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
  const normalized = normalizeContent(pdfContent);
  return Array.isArray(normalized) ? normalized : [normalized];
};

const normalizeContent = (content) => {
  if (Array.isArray(content)) {
    return content.map(normalizeContent).flat();
  }
  if (!content || typeof content !== 'object') {
    return content;
  }
  const next = { ...content };
  next.margin = [0, 0, 0, 0];
  next.lineHeight = 1.05;
  if (next.stack) {
    next.stack = normalizeContent(next.stack);
  }
  if (next.content) {
    next.content = normalizeContent(next.content);
  }
  if (next.table) {
    next.table.body = next.table.body.map((row) =>
      row.map((cell) => normalizeContent(cell))
    );
    next.table.widths = next.table.widths || [];
  }
  return next;
};

const buildSinglePrintContent = ({
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
  const identityStack = identityContent.length
    ? identityContent
    : [{ text: 'Provide the requested identity.', style: 'noteText' }];
  docContent.push({
    table: {
      widths: ['50%', '50%'],
      body: [
        [
          {
            stack: [...identityStack],
            border: [false, false, false, false],
          },
          {
            stack: [
              {
                canvas: [
                  {
                    type: 'rect',
                    x: 0,
                    y: 0,
                    w: 230,
                    h: 20,
                    r: 6,
                    lineWidth: 0.6,
                  },
                ],
                margin: [0, 0, 0, 0],
              },
            ],
            border: [false, false, false, false],
          },
        ],
      ],
    },
    layout: 'noBorders',
    margin: [0, 0, 0, 0],
  });

  printableSlots.forEach(({ slot, problem, index }) => {
    const displayLabel = slot?.label || 'Untitled Slot';
    const slotTitle = `${slot.order || index + 1}: ${displayLabel}`;
    docContent.push({ text: slotTitle, style: 'slotTitle', margin: [0, 4, 0, 1] });
    docContent.push({ text: slot.instruction, style: 'slotInstruction' });
    docContent.push(...convertMarkdownToPdfContent(problem.problem_statement));
    const isRating = slot.response_type === 'rating';
    if (!isRating) {
      docContent.push({
        canvas: [
          {
            type: 'rect',
            x: 0,
            y: 0,
            w: 520,
            h: 100,
            r: 6,
            lineWidth: 0.6,
          },
        ],
        margin: [0, 2, 0, 2],
      });
    }
    if (isRating) {
      const headerCells = [
        { text: 'Description', style: 'tableHeader' },
        ...ratingScaleOptions.map((scale) => ({
          text: scale.label || String(scale.value),
          style: 'tableScaleHeader',
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
      const scaleColumnWidth = `${40 / ratingScaleOptions.length}%`;
      docContent.push({
        table: {
          headerRows: 1,
          widths: ['60%', ...ratingScaleOptions.map(() => scaleColumnWidth)],
          body: tableBody,
        },
        layout: 'lightHorizontalLines',
        margin: [0, 0, 0, 2],
      });
    }
  });

  return docContent;
};

const buildDocDefinition = ({
  printableFilename,
  quiz,
  details,
  ratingCriteria,
  ratingScaleOptions,
  printableCopies,
}) => {
  const safeCopies = Array.isArray(printableCopies) && printableCopies.length > 0
    ? printableCopies
    : [[]];
  const selectionSummaries = safeCopies.map((slots) =>
    Array.from(
      new Set(
        slots
          .map(({ problem }) => problem?.display_label || 'Unknown')
          .filter(Boolean)
      )
    ).join(', ')
  );

  const content = [];
  safeCopies.forEach((slots, copyIndex) => {
    const copyContent = buildSinglePrintContent({
      quiz,
      details,
      printableSlots: slots,
      ratingCriteria,
      ratingScaleOptions,
    });

    const selectionSummary = selectionSummaries[copyIndex] || '';

    // Wrap content in a table to allow repeating footer (via header row with absolute position)
    const copyTable = {
      table: {
        headerRows: 1,
        widths: ['*'],
        body: [
          [
            {
              stack: [
                // Empty text to ensure the header cell is rendered
                { text: ' ', fontSize: 1 },
                // The actual footer text, absolutely positioned
                {
                  text: selectionSummary,
                  alignment: 'right',
                  color: '#888888',
                  italics: true,
                  absolutePosition: { x: 36, y: 780 },
                },
              ],
              margin: [0, 0, 0, 0],
              border: [false, false, false, false],
            },
          ],
          [
            {
              stack: copyContent,
            },
          ],
        ],
      },
      layout: {
        hLineWidth: () => 0,
        vLineWidth: () => 0,
        paddingLeft: () => 0,
        paddingRight: () => 0,
        paddingTop: () => 0,
        paddingBottom: () => 0,
      },
    };

    if (copyIndex < safeCopies.length - 1) {
      copyTable.pageBreak = 'after';
    }

    content.push(copyTable);
  });

  if (typeof window !== 'undefined') {
    window.__quizPrintPageCopyMap = null;
  }

  return {
    pageSize: 'A4',
    pageMargins: [36, 36, 36, 36],
    content,
    // Footer is now handled per-copy via table headers

    styles: {
      printTitle: { fontSize: 12, bold: true },
      slotTitle: { fontSize: 11, bold: true },
      slotInstruction: { fontSize: 10, bold: false, italics: true, margin: [0, 0, 0, 2] },
      sectionLabel: { fontSize: 10, color: '#444444', bold: true, characterSpacing: 0.5 },
      printBody: { fontSize: 10, margin: [0, 0, 0, 2] },
      noteText: { fontSize: 9, color: '#555555' },
      tableHeader: { fontSize: 9, bold: true, fillColor: '#f5f5f5' },
      tableScaleHeader: { fontSize: 6, bold: true, fillColor: '#f5f5f5' },
      tableCell: { fontSize: 9 },
      markdownHeading1: { fontSize: 11, bold: true, margin: [0, 2, 0, 2] },
      markdownHeading2: { fontSize: 10, bold: true, margin: [0, 2, 0, 2] },
      markdownHeading3: { fontSize: 10, bold: true, margin: [0, 2, 0, 2] },
      markdownHeading4: { fontSize: 9, bold: true, margin: [0, 2, 0, 2] },
      markdownHeading5: { fontSize: 9, bold: true, margin: [0, 2, 0, 2] },
      markdownHeading6: { fontSize: 9, bold: true, margin: [0, 2, 0, 2] },
      markdownParagraph: { fontSize: 9, margin: [0, 0, 0, 1] },
      markdownListItem: { fontSize: 9, margin: [0, 0, 0, 1] },
      markdownCode: {
        fontSize: 9,
        font: 'Courier',
        fillColor: '#f3f4f6',
        margin: [0, 1, 0, 2],
        color: '#0f172a',
      },
      markdownBlockquote: {
        italics: true,
        color: '#475569',
        margin: [4, 1, 0, 2],
      },
    },
    defaultStyle: {
      fontSize: 9,
      lineHeight: 1.0,
    },
  };
};

export const previewQuizPdf = ({
  printableFilename,
  quiz,
  details,
  printableCopies,
  ratingCriteria,
  ratingScaleOptions,
}) =>
  new Promise((resolve, reject) => {
    try {
      const definition = buildDocDefinition({
        printableFilename,
        quiz,
        details,
        printableCopies,
        ratingCriteria,
        ratingScaleOptions,
      });
      pdfMake.createPdf(definition).open();
      resolve();
    } catch (error) {
      reject(error);
    }
  });
