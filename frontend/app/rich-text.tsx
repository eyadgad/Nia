import { Fragment, type ReactNode } from "react";

/*
 * Answers arrive as text with a little markdown: bold figures, tables of counts and matched
 * records, numbered lists. It is rendered here rather than with a markdown library so the
 * surface is exactly what NIA writes -- and because every piece becomes a React element,
 * nothing a record or a tester typed is ever interpreted as HTML.
 */

type Align = "left" | "right" | "center";

type Block =
  | { kind: "paragraph"; lines: string[] }
  | { kind: "table"; header: string[]; align: Align[]; rows: string[][] }
  | { kind: "list"; start: number; items: string[] };

const TABLE_ROW = /^\s*\|.*\|\s*$/;
const TABLE_RULE = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$/;
const ORDERED_ITEM = /^\s*(\d+)[.)]\s+(.*)$/;

export function RichText({ text }: { text: string }) {
  return <div className="nia-rich-text">{parseBlocks(text).map(renderBlock)}</div>;
}

function parseBlocks(text: string): Block[] {
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  const blocks: Block[] = [];
  const startsTable = (at: number) =>
    TABLE_ROW.test(lines[at] ?? "") && TABLE_RULE.test(lines[at + 1] ?? "");
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }
    if (startsTable(index)) {
      const header = splitRow(line);
      const align = splitRow(lines[index + 1]).map(alignment);
      const rows: string[][] = [];
      index += 2;
      while (index < lines.length && TABLE_ROW.test(lines[index])) {
        rows.push(splitRow(lines[index]));
        index += 1;
      }
      blocks.push({ kind: "table", header, align, rows });
      continue;
    }
    const ordered = ORDERED_ITEM.exec(line);
    if (ordered) {
      const items: string[] = [];
      while (index < lines.length) {
        const match = ORDERED_ITEM.exec(lines[index]);
        if (!match) break;
        items.push(match[2]);
        index += 1;
      }
      blocks.push({ kind: "list", start: Number(ordered[1]), items });
      continue;
    }
    const paragraph: string[] = [];
    while (
      index < lines.length &&
      lines[index].trim() &&
      !startsTable(index) &&
      !ORDERED_ITEM.test(lines[index])
    ) {
      paragraph.push(lines[index]);
      index += 1;
    }
    blocks.push({ kind: "paragraph", lines: paragraph });
  }
  return blocks;
}

function splitRow(line: string): string[] {
  let body = line.trim();
  if (body.startsWith("|")) body = body.slice(1);
  if (body.endsWith("|") && !body.endsWith("\\|")) body = body.slice(0, -1);
  const cells: string[] = [];
  let current = "";
  for (let at = 0; at < body.length; at += 1) {
    const character = body[at];
    if (character === "\\" && body[at + 1] === "|") {
      current += "|";
      at += 1;
    } else if (character === "|") {
      cells.push(current.trim());
      current = "";
    } else {
      current += character;
    }
  }
  cells.push(current.trim());
  return cells;
}

function alignment(cell: string): Align {
  const rule = cell.trim();
  if (rule.startsWith(":") && rule.endsWith(":")) return "center";
  if (rule.endsWith(":")) return "right";
  return "left";
}

function renderBlock(block: Block, key: number): ReactNode {
  if (block.kind === "table") {
    return (
      <div className="nia-result-table-wrap nia-rich-table" key={key}>
        <table className="nia-result-table">
          <thead>
            <tr>
              {block.header.map((cell, column) => (
                <th key={column} scope="col" style={{ textAlign: block.align[column] ?? "left" }}>
                  {renderInline(cell)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {block.rows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {block.header.map((_, column) => (
                  <td key={column} style={{ textAlign: block.align[column] ?? "left" }}>
                    {renderInline(row[column] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  if (block.kind === "list") {
    return (
      <ol key={key} start={block.start} className="nia-rich-list">
        {block.items.map((item, itemIndex) => (
          <li key={itemIndex}>{renderInline(item)}</li>
        ))}
      </ol>
    );
  }
  return (
    <p key={key}>
      {block.lines.map((line, lineIndex) => (
        <Fragment key={lineIndex}>
          {lineIndex > 0 ? <br /> : null}
          {renderInline(line)}
        </Fragment>
      ))}
    </p>
  );
}

function renderInline(text: string): ReactNode[] {
  const pattern = /\*\*([^*]+?)\*\*|`([^`]+)`/g;
  const out: ReactNode[] = [];
  let last = 0;
  let key = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) out.push(text.slice(last, match.index));
    out.push(
      match[1] !== undefined ? (
        <strong key={key++}>{match[1]}</strong>
      ) : (
        <code key={key++}>{match[2]}</code>
      ),
    );
    last = match.index + match[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}
