from pathlib import Path

p = Path(r"d:\My_New_Stamina\web_star_typing\frontend\src\flightlog\FlightLogPanel.tsx")
t = p.read_text(encoding="utf-8")
t = t.replace(
    '  const [page, setPage] = useState<"stats" | "mt" | "keys">("stats");',
    '  const [page, setPage] = useState<"stats" | "mt">("stats");',
)
t = t.replace(
'''          {([
            ["stats", t("flog_tab_stats")],
            ["mt", t("flog_tab_mt")],
            ["keys", t("flog_tab_keys")],
          ] as const).map(([id, lab]) => (''',
'''          {([
            ["stats", t("flog_tab_stats")],
            ["mt", t("flog_tab_mt")],
          ] as const).map(([id, lab]) => (''',
)
# close stats pane currently after dynamics; move keys inside it
old = '''        <DynamicsChart runs={sum?.runs ?? []} />
      </section>
      </div>
      ) : null}

      {page === "mt" ? (
        <div className="flog-pane flog-pane-mt">
          <MonkeytypePanel />
        </div>
      ) : null}

      {page === "keys" ? (
      <div className="flog-pane flog-pane-keys">
      <div className="flog-bottom">'''
new = '''        <DynamicsChart runs={sum?.runs ?? []} />
      </section>
      <div className="flog-bottom">'''
if old not in t:
    raise SystemExit("merge anchor missing")
t = t.replace(old, new, 1)
t = t.replace(
'''      </div>
      </div>
      ) : null}
    </section>''',
'''      </div>
      </div>
      ) : null}

      {page === "mt" ? (
        <div className="flog-pane flog-pane-mt">
          <MonkeytypePanel />
        </div>
      ) : null}
    </section>''',
1,
)
p.write_text(t, encoding="utf-8")
print("merged")
print("page keys", t.count('"keys"'), "pane-keys", "flog-pane-keys" in t)
