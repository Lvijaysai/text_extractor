// frontend/src/ExportPDF.js
import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";

export const downloadPDF = (data) => {
  const doc = new jsPDF();

  const rows = [
    ["Full Name", data.full_name || "N/A"],
    ["Date of Birth", data.dob || "N/A"],
    ["Father's Name", data.father_name || "N/A"],
    ["Gender", data.gender || "N/A"],
    ["State", data.location?.state || "N/A"],
    ["Pincode", data.location?.pincode || "N/A"],
  ];

  const fullAddress = (
    data.address_details?.full_address ||
    data.address_details?.raw_text ||
    data.address_details?.lines?.join(', ') ||
    ''
  ).trim();

  if (fullAddress) {
    rows.push(["Full Address", fullAddress]);
  }

  autoTable(doc, {
    startY: 40,
    head: [["Field", "Extracted Information"]],
    body: rows,
    theme: "striped",
    headStyles: { fillColor: [41, 128, 185], textColor: 255, fontStyle: "bold" },
    bodyStyles: { textColor: 50 },
    columnStyles: { 0: { fontStyle: "bold", cellWidth: 50 } },
    margin: { top: 40 },
  });

  const pageCount = doc.internal.getNumberOfPages();
  doc.setFontSize(8);

  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    doc.text(`Page ${i} of ${pageCount}`, 196, 285, { align: "right" });
  }

  const fileName = data.full_name
    ? data.full_name.replace(/\s+/g, "_")
    : "Scan_Result";

  doc.save(`VisionOCR_${fileName}.pdf`);
};
