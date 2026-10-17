param([string]$Docx, [string]$Pptx, [string]$OutDir)
New-Item -ItemType Directory -Force $OutDir | Out-Null
if ($Docx) {
  $w = New-Object -ComObject Word.Application
  $w.Visible = $false
  $d = $w.Documents.Open($Docx, $false, $true)
  $pdf = Join-Path $OutDir "report.pdf"
  $d.ExportAsFixedFormat([string]$pdf, 17)
  "pages: " + $d.ComputeStatistics(2)
  $d.Close([ref]0); $w.Quit()
}
if ($Pptx) {
  $p = New-Object -ComObject PowerPoint.Application
  $pr = $p.Presentations.Open($Pptx, $true, $false, $false)
  Get-ChildItem $OutDir -Filter "slide*.png" | Remove-Item
  $i = 1
  foreach ($s in $pr.Slides) { $s.Export((Join-Path $OutDir ("slide{0:D2}.png" -f $i)), "PNG", 1600, 900); $i++ }
  "slides: " + $pr.Slides.Count
  $pr.Close(); $p.Quit()
}
