const getBase64Encoder = () => {
  if (typeof globalThis !== 'undefined' && typeof globalThis.btoa === 'function') {
    return globalThis.btoa.bind(globalThis);
  }
  return null;
};

const getBase64Decoder = () => {
  if (typeof globalThis !== 'undefined' && typeof globalThis.atob === 'function') {
    return globalThis.atob.bind(globalThis);
  }
  return null;
};

export const encodeAttemptToken = (attemptId) => {
  const idNumber = Number(attemptId);
  if (!Number.isFinite(idNumber)) return '';
  const randomSegment = Math.random().toString(36).slice(2, 8);
  const payload = `attempt:${idNumber}:${randomSegment}`;
  const encoder = getBase64Encoder();
  try {
    return encoder ? encoder(payload) : payload;
  } catch (error) {
    return payload;
  }
};

export const decodeAttemptToken = (token) => {
  if (!token) return null;
  const decoder = getBase64Decoder();
  let decoded = token;
  if (decoder) {
    try {
      decoded = decoder(token);
    } catch (error) {
      return null;
    }
  }
  const [prefix, id] = decoded.split(':');
  if (prefix !== 'attempt' || !id) return null;
  const idNumber = Number(id);
  return Number.isFinite(idNumber) ? idNumber : null;
};
