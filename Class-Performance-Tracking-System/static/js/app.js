// Utilities
async function getJSON(url) {
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        return await response.json();
    } catch (e) {
        console.error("Fetch Error:", e);
    }
}

async function postJSON(url, body) {
    try {
        const response = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        return await response.json();
    } catch (e) {
        console.error("Fetch Error:", e);
    }
}

const ymdToDmy = (ymd) => {
    if (!ymd) return "";
    const [y, m, d] = ymd.split("-");
    return `${d}-${m}-${y}`;
};

async function loadSubjects(selectEl) {
    const subs = await getJSON("/api/subjects");
    if (!subs) return;
    selectEl.innerHTML = '<option value="">Select Subject</option>' +
        subs.map(s => `<option value="${s.id}">${s.name}</option>`).join("");
}

// Main logic runs after the page is loaded
document.addEventListener("DOMContentLoaded", () => {
    const page = document.body.dataset.page;

    // --- ATTENDANCE: Store Page ---
    if (page === "store") {
        const subjSel = document.getElementById("subjectSelect");
        const dateInp = document.getElementById("attendanceDate");
        const bodyEl = document.getElementById("studentBody");
        const saveBtn = document.getElementById("saveBtn");
        const statusMsg = document.getElementById("statusMessage");

        const fmtTodayForInput = () => new Date().toISOString().split('T')[0];
        dateInp.value = fmtTodayForInput();

        async function loadStudents(tbodyEl) {
            const sts = await getJSON("/api/students");
            tbodyEl.innerHTML = sts.map((s, idx) => `
                <tr data-student-id="${s.id}">
                <td>${idx + 1}</td>
                <td>${s.roll_no}</td>
                <td>${s.name}</td>
                <td style="text-align:center;"><input type="radio" name="st_${s.id}" value="Present"></td>
                <td style="text-align:center;"><input type="radio" name="st_${s.id}" value="Absent Informed"></td>
                <td style="text-align:center;"><input type="radio" name="st_${s.id}" value="Absent Uninformed"></td>
                </tr>
            `).join("");
        }

        function wireValidation(tbodyEl, saveBtn) {
            const update = () => {
                const rows = [...tbodyEl.querySelectorAll("tr")];
                if (rows.length === 0) {
                    saveBtn.disabled = true;
                    saveBtn.classList.add("disabled");
                    return;
                }
                const allChosen = rows.every(r => {
                    const gid = r.getAttribute("data-student-id");
                    return !!r.querySelector(`input[name="st_${gid}"]:checked`);
                });
                saveBtn.disabled = !allChosen;
                saveBtn.classList.toggle("disabled", !allChosen);
            };
            tbodyEl.addEventListener("change", update);
            update();
        }

        loadSubjects(subjSel);
        wireValidation(bodyEl, saveBtn);

        const checkExistingAttendance = async () => {
            const subject_id = subjSel.value;
            const selectedDate = dateInp.value;
            if (!subject_id || !selectedDate) {
                bodyEl.innerHTML = "";
                statusMsg.innerHTML = "Please select a subject and a date.";
                wireValidation(bodyEl, saveBtn);
                return;
            }
            await loadStudents(bodyEl);
            const date = ymdToDmy(selectedDate);
            const data = await getJSON(`/api/get_attendance_for_store?subject_id=${subject_id}&date=${date}`);
            
            if (data && data.ok && data.records) {
                let attendanceTaken = false;
                data.records.forEach(record => {
                    if (record.status !== 'none') {
                        attendanceTaken = true;
                        const radio = document.querySelector(`tr[data-student-id="${record.student_id}"] input[value="${record.status}"]`);
                        if (radio) radio.checked = true;
                    }
                });
                if (attendanceTaken) {
                    statusMsg.innerHTML = `✅ Attendance for ${date} already exists. You can edit it.`;
                } else {
                    statusMsg.innerHTML = `ℹ️ No attendance found for ${date}. Please mark it below.`;
                }
                wireValidation(bodyEl, saveBtn);
            }
        };
        
        subjSel.addEventListener("change", checkExistingAttendance);
        dateInp.addEventListener("change", checkExistingAttendance);

        document.getElementById("attendanceForm").addEventListener("submit", async (e) => {
            e.preventDefault();
            const date = ymdToDmy(dateInp.value);
            const subject_id = parseInt(subjSel.value, 10);
            if (!subject_id || !date) {
                alert("Please select a subject and a date first.");
                return;
            }
            const marks = [...bodyEl.querySelectorAll("tr")].map(r => {
                const sid = parseInt(r.getAttribute("data-student-id"), 10);
                const status = r.querySelector(`input[name="st_${sid}"]:checked`).value;
                return { student_id: sid, status };
            });
            const resp = await postJSON("/api/save_attendance", { date, subject_id, marks });
            if (resp && resp.ok) {
                alert("✅ Attendance stored successfully!");
                statusMsg.innerHTML = `✅ Attendance for ${date} already exists. You can edit it.`;
            } else {
                alert("❌ Failed to store: " + (resp.error || "Unknown error"));
            }
        });
    }

    // --- ATTENDANCE: View Page ---
    if (page === "view") {
        const subjSel = document.getElementById("viewSubject");
        const showBtn = document.getElementById("showRecords");
        const area = document.getElementById("recordsArea");
        const filterTypeSel = document.getElementById("filterType");
        const dateControls = document.getElementById("dateFilterControls");
        const monthControls = document.getElementById("monthFilterControls");
        const yearControls = document.getElementById("yearFilterControls");
        const dateInp = document.getElementById("viewDate");
        const monthYearInp = document.getElementById("viewYearMonth");
        const monthInp = document.getElementById("viewMonth");
        const yearInp = document.getElementById("viewYear");
        
        const currentYear = new Date().getFullYear();
        monthYearInp.value = currentYear;
        yearInp.value = currentYear;

        loadSubjects(subjSel);

        filterTypeSel.addEventListener("change", () => {
            dateControls.style.display = "none";
            monthControls.style.display = "none";
            yearControls.style.display = "none";
            if (filterTypeSel.value === "date") dateControls.style.display = "inline";
            if (filterTypeSel.value === "month") monthControls.style.display = "inline";
            if (filterTypeSel.value === "year") yearControls.style.display = "inline";
        });

        showBtn.addEventListener("click", async () => {
            const subject_id = parseInt(subjSel.value, 10);
            if (!subject_id) {
                alert("Please select a subject.");
                return;
            }
            const filterType = filterTypeSel.value;
            const params = new URLSearchParams({ subject_id, filter_type: filterType });
            let reportTitle = `Records for ${subjSel.options[subjSel.selectedIndex].text}`;

            if (filterType === "date") {
                const dmy = ymdToDmy(dateInp.value);
                if (!dmy) { alert("Please pick a date."); return; }
                params.append("date", dmy);
                reportTitle += ` on ${dmy}`;
            } else if (filterType === "month") {
                const year = monthYearInp.value;
                const month = monthInp.value;
                if (!year) { alert("Please enter a year."); return; }
                params.append("year", year);
                params.append("month", month);
                const monthName = monthInp.options[monthInp.selectedIndex].text;
                reportTitle += ` for ${monthName} ${year}`;
            } else if (filterType === "year") {
                const year = yearInp.value;
                if (!year) { alert("Please enter a year."); return; }
                params.append("year", year);
                reportTitle += ` for the year ${year}`;
            }

            area.innerHTML = "<p>Loading...</p>";
            const data = await getJSON(`/api/get_attendance?${params.toString()}`);

            if (!data || !data.ok) {
                area.innerHTML = `<p>Error: ${data.error || "failed"}</p>`;
                return;
            }
            const rows = data.records;
            if (!rows || rows.length === 0) {
                area.innerHTML = `<p>No records found for the selected criteria.</p>`;
                return;
            }

            let html = `<h3>${reportTitle}</h3>`;
            if (filterType === "date") {
                const allAbsent = rows.every(r => r.status === 'Absent Uninformed');
                if (allAbsent) {
                    area.innerHTML = `<p>No attendance has been taken for this date.</p>`;
                    return;
                }
                html += `<table class="table"><thead><tr><th>S.No</th><th>Roll No</th><th>Name</th><th>Status</th></tr></thead><tbody>`;
                rows.forEach((r, i) => {
                    html += `<tr><td>${i+1}</td><td>${r.roll_no}</td><td>${r.name}</td><td>${r.status}</td></tr>`;
                });
            } else {
                html += `<table class="table"><thead><tr><th>S.No</th><th>Date</th><th>Roll No</th><th>Name</th><th>Status</th></tr></thead><tbody>`;
                rows.forEach((r, i) => {
                    html += `<tr><td>${i+1}</td><td>${r.date}</td><td>${r.roll_no}</td><td>${r.name}</td><td>${r.status}</td></tr>`;
                });
            }
            html += `</tbody></table>`;
            area.innerHTML = html;
        });
    }

    // --- ATTENDANCE: Individual Report Page ---
    if (page === "individual") {
        const subjectSelect = document.getElementById("subjectSelect");
        loadSubjects(subjectSelect).then(() => {
            subjectSelect.options[0].textContent = 'All Subjects';
        });

        const dateType = document.getElementById("dateType");
        const yearInput = document.getElementById("yearInput");
        const monthInput = document.getElementById("monthInput");
        const dateInput = document.getElementById("dateInput");

        dateType.addEventListener("change", function() {
            yearInput.style.display = "none";
            monthInput.style.display = "none";
            dateInput.style.display = "none";
            if (this.value === "year") yearInput.style.display = "inline-block";
            if (this.value === "month") monthInput.style.display = "inline-block";
            if (this.value === "date") dateInput.style.display = "inline-block";
        });

        document.getElementById("searchBtn").addEventListener("click", async () => {
            const q = document.getElementById("searchQuery");
            const info = document.getElementById("studentInfo");
            const rep = document.getElementById("studentReport");
            const totalDaysInput = document.getElementById("totalDays");
            const query = q.value.trim();
            const totalDays = parseInt(totalDaysInput.value, 10);

            if (!query) { info.innerHTML = "<p>Please enter a name or roll number.</p>"; return; }
            if (!totalDays || totalDays <= 0) { info.innerHTML = "<p>Please enter a valid number for Total Working Days.</p>"; return; }

            const params = new URLSearchParams({
                query,
                subject_id: subjectSelect.value,
                dateType: dateType.value,
                year: yearInput.value,
                month: monthInput.value,
                date: dateInput.value,
            });

            info.innerHTML = "Searching…";
            rep.innerHTML = "";
            const data = await getJSON(`/api/student_report?${params.toString()}`);
            
            if (!data || !data.ok) { info.innerHTML = `<p>Error: ${data.error || "failed"}</p>`; return; }
            if (!data.student) { info.innerHTML = `<p>No matching student found.</p>`; return; }
            
            const s = data.student;
            const daysPresent = data.days_present;
            const percentage = (daysPresent / totalDays) * 100;
            const percentageColor = percentage >= 75 ? 'green' : 'red';

            info.innerHTML = `
                <div style="text-align:left; padding:15px; border: 1px solid #ddd; border-radius: 5px;">
                    <strong>${s.name}</strong> — Roll No: <strong>${s.roll_no}</strong>
                    <hr style="border:0; border-top:1px solid #ddd; margin: 8px 0;">
                    Days Present: <strong>${daysPresent}</strong> out of <strong>${totalDays}</strong> working days.
                    <br>
                    Attendance Percentage: <strong style="color: ${percentageColor}; font-size: 1.1em;">${percentage.toFixed(2)}%</strong>
                </div>`;

            const rows = data.rows;
            if (rows.length === 0) {
                rep.innerHTML = "<p>No attendance records found for the selected criteria.</p>";
                return;
            }
            let html = `<h4>Detailed Records</h4><table class="table"><thead><tr><th>S.No</th><th>Date</th><th>Subject</th><th>Status</th></tr></thead><tbody>`;
            rows.forEach((r, i) => {
                html += `<tr><td>${i+1}</td><td>${r.date}</td><td>${r.subject}</td><td>${r.status}</td></tr>`;
            });
            html += `</tbody></table>`;
            rep.innerHTML = html;
        });
    }

    // --- HOMEWORK: Manage Page ---
    if (page === 'manage_homework') {
        const subjectSel = document.getElementById('hwSubject');
        const form = document.getElementById('homeworkForm');
        const homeworkIdField = document.getElementById('homeworkId');
        const formTitle = document.getElementById('form-title');
        const submitBtn = document.getElementById('submitBtn');
        const cancelBtn = document.getElementById('cancelBtn');
        const homeworkTable = document.getElementById('homeworkTable');

        loadSubjects(subjectSel);

        const resetForm = () => {
            form.reset();
            homeworkIdField.value = '';
            formTitle.textContent = 'Post New Homework';
            submitBtn.textContent = 'Save Homework';
            cancelBtn.style.display = 'none';
        };

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const homeworkId = homeworkIdField.value;
            const data = {
                subject_id: subjectSel.value,
                description: document.getElementById('hwDescription').value,
                due_date: document.getElementById('hwDueDate').value,
            };

            let resp;
            if (homeworkId) { // UPDATE
                resp = await postJSON(`/api/homework/${homeworkId}`, data);
            } else { // ADD
                resp = await postJSON('/api/homework', data);
            }

            if (resp && resp.ok) {
                alert(`Homework ${homeworkId ? 'updated' : 'posted'} successfully!`);
                location.reload();
            } else {
                alert('Error: Operation failed.');
            }
        });

        homeworkTable.addEventListener('click', async (e) => {
            const target = e.target;
            const row = target.closest('tr');
            if (!row) return;
            const homeworkId = row.dataset.homeworkId;

            if (target.classList.contains('btn-delete')) {
                if (confirm('Are you sure you want to delete this assignment?')) {
                    const resp = await fetch(`/api/homework/${homeworkId}`, { method: 'DELETE' });
                    if (resp.ok) {
                        row.remove();
                    } else {
                        alert('Failed to delete.');
                    }
                }
            }

            if (target.classList.contains('btn-edit')) {
                const cells = row.querySelectorAll('td');
                homeworkIdField.value = homeworkId;
                subjectSel.value = cells[1].dataset.subjectId;
                document.getElementById('hwDescription').value = cells[2].textContent;
                const [d, m, y] = cells[3].textContent.split('-');
                document.getElementById('hwDueDate').value = `${y}-${m}-${d}`;
                
                formTitle.textContent = 'Edit Homework';
                submitBtn.textContent = 'Update Homework';
                cancelBtn.style.display = 'inline-block';
                window.scrollTo(0, 0);
            }
        });
        cancelBtn.addEventListener('click', resetForm);
    }

    // --- HOMEWORK: Status Page ---
    if (page === 'homework_status') {
        document.querySelector('.homework-status-list').addEventListener('change', async (e) => {
            if (e.target.classList.contains('status-toggle')) {
                const checkbox = e.target;
                const homeworkItem = checkbox.closest('.homework-item');
                const homeworkId = homeworkItem.dataset.homeworkId;
                const status = checkbox.checked ? 'Completed' : 'Pending';

                const resp = await postJSON('/api/homework_status', { homework_id: homeworkId, status });
                if (resp && resp.ok) {
                    homeworkItem.classList.toggle('completed', checkbox.checked);
                } else {
                    alert('Failed to update status. Please try again.');
                    checkbox.checked = !checkbox.checked;
                }
            }
        });
    }
});