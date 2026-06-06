/* ============================================================
   EmptyScreen — Sprint 0 placeholder for each of the 14 routes.
   Renders a titled empty panel so navigation is verifiable before
   feature modules land. Each later sprint replaces this with the real screen.
   ============================================================ */
import { Icon, type IconKey } from "@/lib/icons";

export function EmptyScreen({
  name,
  screen,
  icon = "i-home",
}: {
  name: string;
  screen: string;
  icon?: IconKey;
}) {
  return (
    <section className="empty-screen" data-testid="empty-screen" data-screen={screen}>
      <div className="es-icon">
        <Icon name={icon} />
      </div>
      <h1>{name}</h1>
      <span className="es-tag">{screen}</span>
      <span className="es-meta">Màn hình đang chờ module — sẽ hoàn thiện ở sprint sau.</span>
    </section>
  );
}
