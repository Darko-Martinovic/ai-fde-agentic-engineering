import type { ReactNode } from "react";

/** The top of a page: its title, a line on what it's for, and its main
 *  action, if it has one. */
export function PageHeader({
  title,
  purpose,
  action,
}: Readonly<{ title: string; purpose: string; action?: ReactNode }>) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        <p>{purpose}</p>
      </div>
      {action && <div className="page-header__action">{action}</div>}
    </header>
  );
}
