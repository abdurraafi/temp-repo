// STEP 1: Get input config and record from Airtable
let inputConfig = input.config();
let recordId = inputConfig.recordId;

console.log("🔍 Starting script for record ID:", recordId);

let table = base.getTable("SUBSTITUTE_SYSTEM");
let record = await table.selectRecordAsync(recordId);

if (!record) {
    throw new Error("❌ Record not found. Make sure the record ID is passed in correctly.");
}

console.log("✅ Record fetched:", record.name);

// STEP 2: Define timetable slot mappings
const slotMapping = {
    "M1": { days: [1, 3], time: "13:00" },  // 8:00 AM CST
    "M2": { days: [1, 3], time: "14:45" },  // 9:45 AM CST
    "M3": { days: [1, 3], time: "16:30" },  // 11:30 AM CST
    "M4": { days: [1, 3], time: "18:15" },  // 1:15 PM CST
    "M5": { days: [1, 3], time: "20:00" },  // 3:00 PM CST
    "M6": { days: [1, 3], time: "21:45" },  // 4:45 PM CST

    "T1": { days: [2, 4], time: "13:00" },
    "T2": { days: [2, 4], time: "14:45" },
    "T3": { days: [2, 4], time: "16:30" },
    "T4": { days: [2, 4], time: "18:15" },
    "T5": { days: [2, 4], time: "20:00" },
    "T6": { days: [2, 4], time: "21:45" }
};
// STEP 3: Get field values
let startDate = new Date(record.getCellValue("START_DATE"));
let endDate = new Date(record.getCellValue("END_DATE"));
let slot = record.getCellValue("TIMETABLE_SLOTS");
let generateSessions = record.getCellValue("GENERATE_SESSIONS");

console.log("📆 Start Date:", startDate);
console.log("📆 End Date:", endDate);
console.log("📚 Slot:", slot);
console.log("✅ Checkbox status:", generateSessions);

if (!generateSessions || !slotMapping[slot]) {
    console.log("⛔ Skipping: Checkbox not checked or invalid slot.");
    return;
}

let { days, time } = slotMapping[slot];
console.log("🗓️ Matching days of week:", days);
console.log("⏰ Time for slot:", time);

// STEP 4: Parse date + time into a full datetime object
function parseDateTime(baseDate, timeString) {
    const [hourStr, minuteStr] = timeString.split(":");
    const hour = parseInt(hourStr, 10);
    const minute = parseInt(minuteStr, 10);

    const date = new Date(
        baseDate.getFullYear(),
        baseDate.getMonth(),
        baseDate.getDate(),
        hour,
        minute,
        0,
        0
    );

    return date;
}

// STEP 5: Generate matching dates
let currentDate = new Date(startDate);
let matchingDates = [];

while (currentDate <= endDate) {
    let dayOfWeek = currentDate.getDay(); // 0 = Sunday
    if (days.includes(dayOfWeek)) {
    const baseDate = new Date(currentDate.getTime());
    const classDate = parseDateTime(baseDate, time);
    console.log(`📍 Matched date: ${classDate.toISOString()}`);
    matchingDates.push(classDate);
    }
    currentDate.setDate(currentDate.getDate() + 1);
}

console.log(`✅ Total matching class dates: ${matchingDates.length}`);

// STEP 6: Prepare linked record format for COURSE_LIST
let courseListLinks = record.getCellValue("COURSE_LIST");
let courseListLinkedObjects = Array.isArray(courseListLinks)
    ? courseListLinks.map(link => ({ id: link.id }))
    : [];

console.log("🔗 Linked COURSE_LIST IDs:", courseListLinkedObjects.map(obj => obj.id));

// STEP 7: Create session records
for (let date of matchingDates) {
    console.log("🛠️ Creating record for:", date.toISOString());

    await table.createRecordAsync({
        "DATE_OF_CLASS": date,
        "COURSE_LIST": courseListLinkedObjects,
        "SUB_LESSON_PLAN_LINK": record.getCellValue("SUB_LESSON_PLAN_LINK")
    });
}

// STEP 8: Uncheck checkbox
console.log("🧹 Unchecking checkbox...");
await table.updateRecordAsync(record.id, {
    "GENERATE_SESSIONS": false
});

console.log(`🎉 Done! Created ${matchingDates.length} class session(s).`);
