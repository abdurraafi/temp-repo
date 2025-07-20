// Script for Airtable Automation triggered by checkbox

let config = input.config(); // ✅ gets the automation input
let addDropRecordId = config.recordId; // ✅ this works ONLY if you've added 'recordId' properly



if (!addDropRecordId) {
    throw new Error("No recordId passed into script input.");
}

// 1. Get ADD_DROP table and record
let addDropTable = base.getTable("ADD_DROP");
let addDropRecord = await addDropTable.selectRecordAsync(addDropRecordId);

if (!addDropRecord) {
    throw new Error(`ADD_DROP record with ID ${addDropRecordId} not found.`);
}

// 2. Get linked student record
let studentLinked = addDropRecord.getCellValue("STUDENT_ROSTER");
if (!studentLinked || studentLinked.length === 0) {
    throw new Error("No student linked to this ADD_DROP record.");
}
let studentRecordId = studentLinked[0].id;

// 3. Get ADD and DROP linked records
let addRecords = addDropRecord.getCellValue("ADD") || [];
let dropRecords = addDropRecord.getCellValue("DROP") || [];

// 4. Load the student record from STUDENT_LIST
let studentTable = base.getTable("STUDENT_LIST");
let studentRecord = await studentTable.selectRecordAsync(studentRecordId);

if (!studentRecord) {
    throw new Error(`Student record with ID ${studentRecordId} not found.`);
}

// 5. Get current enrollments
let nextEnrollments = studentRecord.getCellValue("NEXT_YEAR_ENROLLMENTS") || [];
let nextIds = new Set(nextEnrollments.map(e => e.id));
let dropIds = new Set(dropRecords.map(e => e.id));

// 6. Remove courses listed in DROP
for (let id of dropIds) {
    nextIds.delete(id);
}

// 7. Add courses listed in ADD
for (let record of addRecords) {
    nextIds.add(record.id);
}

// 8. Prepare updated enrollments
let updatedEnrollments = [...nextIds].map(id => ({ id }));

// 9. Update the student record
await studentTable.updateRecordAsync(studentRecord.id, {
    "NEXT_YEAR_ENROLLMENTS": updatedEnrollments
});
