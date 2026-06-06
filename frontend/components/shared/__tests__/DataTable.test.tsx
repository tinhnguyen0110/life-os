import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DataTable, type Column } from "../DataTable";

interface Row {
  id: string;
  name: string;
  n: number;
}

const columns: Column<Row>[] = [
  { key: "name", header: "Tên", cell: (r) => r.name, className: "pn" },
  { key: "n", header: "Số", cell: (r) => r.n },
];

const rows: Row[] = [
  { id: "a", name: "Alpha", n: 1 },
  { id: "b", name: "Beta", n: 2 },
];

describe("DataTable", () => {
  it("renders headers and a row per item", () => {
    render(<DataTable columns={columns} rows={rows} rowKey={(r) => r.id} />);
    expect(screen.getByText("Tên")).toBeInTheDocument();
    expect(screen.getByText("Số")).toBeInTheDocument();
    expect(screen.getAllByTestId("datatable-row")).toHaveLength(2);
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
  });

  it("applies a column className to its cells", () => {
    const { container } = render(
      <DataTable columns={columns} rows={rows} rowKey={(r) => r.id} />,
    );
    expect(container.querySelectorAll("td.pn")).toHaveLength(2);
  });

  it("shows the empty state (not a bare table) when rows is empty", () => {
    render(
      <DataTable
        columns={columns}
        rows={[]}
        rowKey={(r) => r.id}
        emptyLabel="Chưa có dự án nào."
      />,
    );
    expect(screen.getByTestId("datatable-empty")).toHaveTextContent("Chưa có dự án nào.");
    expect(screen.queryByTestId("datatable")).toBeNull();
  });

  it("fires onRowClick with the clicked row and marks rows clickable", async () => {
    const onRowClick = vi.fn();
    const user = userEvent.setup();
    render(
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(r) => r.id}
        onRowClick={onRowClick}
      />,
    );
    const firstRow = screen.getAllByTestId("datatable-row")[0];
    expect(firstRow.className).toContain("clickable");
    expect(firstRow).toHaveAttribute("role", "button");
    await user.click(firstRow);
    expect(onRowClick).toHaveBeenCalledTimes(1);
    expect(onRowClick).toHaveBeenCalledWith(rows[0], 0);
  });

  it("rows are NOT clickable when no handler is given", () => {
    render(<DataTable columns={columns} rows={rows} rowKey={(r) => r.id} />);
    const firstRow = screen.getAllByTestId("datatable-row")[0];
    expect(firstRow.className || "").not.toContain("clickable");
    expect(firstRow).not.toHaveAttribute("role");
  });

  it("activates a row via keyboard (Enter)", async () => {
    const onRowClick = vi.fn();
    const user = userEvent.setup();
    render(
      <DataTable columns={columns} rows={rows} rowKey={(r) => r.id} onRowClick={onRowClick} />,
    );
    const firstRow = screen.getAllByTestId("datatable-row")[0];
    firstRow.focus();
    await user.keyboard("{Enter}");
    expect(onRowClick).toHaveBeenCalledWith(rows[0], 0);
  });
});
