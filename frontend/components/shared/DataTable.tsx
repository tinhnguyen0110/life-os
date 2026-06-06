"use client";
/* ============================================================
   DataTable — generic table wrapping the mock `.dtable` markup.
   Columns define header + a per-row cell renderer; rows are arbitrary objects.
   Optional `onRowClick` makes rows .clickable (mock `tr.clickable` hover/cursor).
   Handles the empty state (no rows) with a centered hint instead of a bare
   <tbody> — every data view must show empty/loading/error (playbook rule).
   ============================================================ */
import type { ReactNode } from "react";

export interface Column<Row> {
  /** stable key (also used as React key for the cell). */
  key: string;
  /** header label (rendered in .dtable thead). */
  header: ReactNode;
  /** cell renderer for this column. */
  cell: (row: Row, index: number) => ReactNode;
  /** optional <td> className (e.g. "pn" for the bold name column). */
  className?: string;
}

export function DataTable<Row>({
  columns,
  rows,
  rowKey,
  onRowClick,
  emptyLabel = "Chưa có dữ liệu.",
}: {
  columns: Column<Row>[];
  rows: Row[];
  /** unique key per row (id). */
  rowKey: (row: Row, index: number) => string;
  /** if set, rows become clickable (cursor + hover) and fire this on click. */
  onRowClick?: (row: Row, index: number) => void;
  /** shown when rows is empty. */
  emptyLabel?: ReactNode;
}) {
  if (rows.length === 0) {
    return (
      <div className="hint" style={{ padding: "18px 16px" }} data-testid="datatable-empty">
        {emptyLabel}
      </div>
    );
  }

  return (
    <table className="dtable" data-testid="datatable">
      <thead>
        <tr>
          {columns.map((c) => (
            <th key={c.key}>{c.header}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => {
          const clickable = !!onRowClick;
          return (
            <tr
              key={rowKey(row, i)}
              className={clickable ? "clickable" : undefined}
              onClick={clickable ? () => onRowClick!(row, i) : undefined}
              onKeyDown={
                clickable
                  ? (e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onRowClick!(row, i);
                      }
                    }
                  : undefined
              }
              tabIndex={clickable ? 0 : undefined}
              role={clickable ? "button" : undefined}
              data-testid="datatable-row"
            >
              {columns.map((c) => (
                <td key={c.key} className={c.className}>
                  {c.cell(row, i)}
                </td>
              ))}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
