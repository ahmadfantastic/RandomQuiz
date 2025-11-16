import DOMPurify from 'dompurify';
import { marked } from 'marked';

marked.setOptions({ mangle: false });

export const renderProblemMarkupHtml = (statement) => {
  if (!statement) {
    return '';
  }
  try {
    const dirty = marked.parse(statement);
    return DOMPurify.sanitize(dirty);
  } catch {
    return '';
  }
};
