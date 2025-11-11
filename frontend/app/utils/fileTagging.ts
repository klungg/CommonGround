export interface ParsedTagSegment {
  tag: string;
  /** Zero-based index of the '@' trigger */
  start: number;
  /** Exclusive end index of the segment */
  end: number;
  /** Unescaped relative path (without the leading '@') */
  path: string;
}

export interface TriggerSegment {
  start: number;
  end: number;
  query: string;
  fullSegment: string;
}

const TRIGGER_CHAR = '@';

export function normalizeRelativePath(input: string): string {
  if (!input) {
    return '';
  }
  let value = input.trim();
  if (value.startsWith('./')) {
    value = value.slice(2);
  }
  if (value.startsWith('/')) {
    value = value.slice(1);
  }
  value = value.replace(/\\/g, '/');
  if (value.endsWith('/**')) {
    value = value.slice(0, -3);
  }
  if (value.endsWith('/')) {
    value = value.slice(0, -1);
  }
  return value;
}

export function escapePath(filePath: string): string {
  let result = '';
  for (let i = 0; i < filePath.length; i += 1) {
    const char = filePath[i];
    if (char === ' ' && (i === 0 || filePath[i - 1] !== '\\')) {
      result += '\\ ';
    } else {
      result += char;
    }
  }
  return result;
}

export function unescapePath(filePath: string): string {
  return filePath.replace(/\\ /g, ' ');
}

function isWhitespace(char: string): boolean {
  return /\s/.test(char);
}

export function findActiveTriggerSegment(value: string, cursor: number): TriggerSegment | null {
  if (cursor > value.length) {
    cursor = value.length;
  }

  let searchIndex = cursor - 1;
  let sawEscape = false;

  while (searchIndex >= 0) {
    const char = value[searchIndex];
    if (char === '\\' && !sawEscape) {
      sawEscape = true;
      searchIndex -= 1;
      continue;
    }
    if (char === TRIGGER_CHAR && !sawEscape) {
      break;
    }
    if (isWhitespace(char)) {
      return null;
    }
    sawEscape = false;
    searchIndex -= 1;
  }

  if (searchIndex < 0 || value[searchIndex] !== TRIGGER_CHAR) {
    return null;
  }

  const start = searchIndex;
  let end = start + 1;
  let inEscape = false;
  while (end < value.length) {
    const char = value[end];
    if (inEscape) {
      inEscape = false;
      end += 1;
      continue;
    }
    if (char === '\\') {
      inEscape = true;
      end += 1;
      continue;
    }
    if (isWhitespace(char)) {
      break;
    }
    end += 1;
  }

  const segment = value.slice(start + 1, end);
  const query = value.slice(start + 1, cursor);

  return {
    start,
    end,
    query: unescapePath(query),
    fullSegment: segment,
  };
}

export function extractFileTags(value: string): ParsedTagSegment[] {
  const tags: ParsedTagSegment[] = [];
  let index = 0;
  while (index < value.length) {
    if (value[index] !== TRIGGER_CHAR || (index > 0 && value[index - 1] === '\\')) {
      index += 1;
      continue;
    }

    let end = index + 1;
    let inEscape = false;
    while (end < value.length) {
      const char = value[end];
      if (inEscape) {
        inEscape = false;
        end += 1;
        continue;
      }
      if (char === '\\') {
        inEscape = true;
        end += 1;
        continue;
      }
      if (isWhitespace(char)) {
        break;
      }
      end += 1;
    }

    if (end === index + 1) {
      index = end;
      continue;
    }

    const segment = value.slice(index, end);
    const path = unescapePath(segment.slice(1));
    tags.push({
      tag: segment,
      start: index,
      end,
      path,
    });

    index = end;
  }
  return tags;
}

export function replaceSegment(value: string, segment: TriggerSegment, replacement: string): string {
  return [
    value.slice(0, segment.start + 1),
    replacement,
    value.slice(segment.end),
  ].join('');
}
