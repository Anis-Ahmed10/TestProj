import { Table, TableProps } from "antd";
import { ColumnsType, ExpandableConfig } from "antd/es/table/interface";
import { JSX } from "react";
import { AnyObject } from "antd/es/_util/type";

interface AITableProps<T> {
  columns: ColumnsType<T>;
  datasource: T[];
  loading?: boolean;
  rowSelection?: TableProps<T>["rowSelection"];
  pageSize?: number;
  showPagination?: boolean;
  // Full pagination config; pass this for server-side paging (controlled current
  // page + total). When set it takes precedence over showPagination/pageSize.
  pagination?: TableProps<T>["pagination"];
  rowClassName?: (record: T) => string;
  expandable?: ExpandableConfig<T>;
  rowKey?: string | ((record: T) => string);
  onChange?: TableProps<T>["onChange"];
}

const AITable = <T extends AnyObject>({
  columns,
  datasource,
  loading = false,
  rowSelection,
  pageSize = 10,
  showPagination = true,
  pagination,
  rowClassName,
  expandable,
  rowKey,
  onChange,
}: AITableProps<T>): JSX.Element => {
  return (
    <Table
      columns={columns}
      dataSource={datasource}
      loading={loading}
      rowSelection={rowSelection}
      rowKey={rowKey || ((record) => record.id)}
      pagination={
        pagination ??
        (showPagination ? { pageSize, placement: ["bottomCenter"] } : false)
      }
      rowClassName={rowClassName}
      expandable={expandable}
      onChange={onChange}
    />
  );
};

export default AITable;
