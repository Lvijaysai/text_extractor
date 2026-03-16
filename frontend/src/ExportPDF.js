// frontend/src/ExportPDF.js
import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable"; // Import the default export

export const downloadPDF = (data) => {
  const doc = new jsPDF();

  // ... (Header code remains the same) ...

  // 2. Prepare Data Table
  const tableRows = [
    ["Field", "Extracted Information"],
    ["Full Name", data.full_name || "N/A"],
    ["Date of Birth", data.dob || "N/A"],
    ["Father's Name", data.father_name || "N/A"],
    ["Gender", data.gender || "N/A"],
    ["State", data.location?.state || "N/A"],
    ["Pincode", data.location?.pincode || "N/A"],
    ["Full Address", data.address_details?.full_address || "N/A"],
  ];

  // 3. Generate Table
  // USE autoTable(doc, { ... }) instead of doc.autoTable({ ... })
  autoTable(doc, {
    startY: 40,
    head: [tableRows[0]],
    body: tableRows.slice(1),
    theme: 'striped',
    headStyles: { fillColor: [41, 128, 185], textColor: 255, fontStyle: 'bold' },
    bodyStyles: { textColor: 50 },
    columnStyles: { 0: { fontStyle: 'bold', cellWidth: 50 } },
    margin: { top: 40 },
  });

  // 4. Footer & 5. Save (remains the same)
  const pageCount = doc.internal.getNumberOfPages();
  doc.setFontSize(8);
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    doc.text(`Page ${i} of ${pageCount}`, 196, 285, { align: "right" });
  }

  const fileName = data.full_name ? data.full_name.replace(/\s+/g, '_') : 'Scan_Result';
  doc.save(`VisionOCR_${fileName}.pdf`);
};