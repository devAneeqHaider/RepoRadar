export default function StatCards({ stats = {}, stars, language }) {
  const cards = [
    { label: "Files", value: stats.file_count ?? 0 },
    { label: "Modules", value: stats.module_count ?? 0 },
    { label: "Classes", value: stats.class_count ?? 0 },
    { label: "Functions", value: stats.function_count ?? 0 },
  ];

  if (stars !== undefined && stars !== null) {
    cards.push({ label: "Stars", value: stars });
  }
  if (language) {
    cards.push({ label: "Language", value: language, text: true });
  }

  return (
    <div className="stat-grid">
      {cards.map((card) => (
        <div className="stat-card" key={card.label}>
          <div className="stat-value">
            {card.text
              ? card.value
              : Number(card.value).toLocaleString("en-US")}
          </div>
          <div className="stat-label">{card.label}</div>
        </div>
      ))}
    </div>
  );
}
