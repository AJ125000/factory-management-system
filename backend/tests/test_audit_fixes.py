from io import BytesIO

from openpyxl import load_workbook


def test_excel_export_never_turns_typed_text_into_formulas(api):
    w = api.worker('=HYPERLINK("http://evil","pay")')
    api.rate("machine_operator", "cutting", "1.5", "2026-01-01")
    api.entry(w, "2026-01-05")
    resp = api.c.get("/api/exports/wages.xlsx", params={"start": "2026-01-01", "end": "2026-01-31"})
    wb = load_workbook(BytesIO(resp.content))
    cells = [c for ws in wb.worksheets for row in ws.iter_rows() for c in row]
    assert not [c.coordinate for c in cells if c.data_type == "f"]
    assert any(c.value == '=HYPERLINK("http://evil","pay")' for c in cells)  # kept as text


def test_backup_copy_folder_must_be_a_full_path(api, tmp_path):
    relative = api.c.patch("/api/settings", json={"backup_copy_dir": "."})
    assert relative.json()["error"]["details"]["reason"] == "backup_dir_missing"
    assert api.c.patch("/api/settings", json={"backup_copy_dir": str(tmp_path)}).status_code == 200
