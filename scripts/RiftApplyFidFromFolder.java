// Ghidra helper script, which attaches a folder of RIFT-generated Function ID
// databases and re-applies Function ID matching to the current program.
// The Ghidra counterpart of scripts/ida_apply_flirt_from_folder.py.
// Drop this in your Ghidra scripts directory and run it on an open program.
//@category FunctionID
import java.io.File;

import ghidra.app.script.GhidraScript;
import ghidra.app.util.importer.MessageLog;
import ghidra.feature.fid.analyzer.FidAnalyzer;
import ghidra.feature.fid.db.FidFile;
import ghidra.feature.fid.db.FidFileManager;

public class RiftApplyFidFromFolder extends GhidraScript {

	private static final String FIDB_EXTENSION = ".fidb";

	@Override
	protected void run() throws Exception {
		if (currentProgram == null) {
			printerr("No program is open. Open a Rust binary first.");
			return;
		}

		File folder = askDirectory("Select folder containing RIFT .fidb files", "Select");
		File[] files = folder.listFiles();
		if (files == null) {
			printerr("Could not list " + folder.getAbsolutePath());
			return;
		}

		int attached = 0;
		FidFileManager fidFileManager = FidFileManager.getInstance();
		for (File file : files) {
			if (!file.getName().toLowerCase().endsWith(FIDB_EXTENSION)) {
				continue;
			}
			println("Attaching Function ID database = " + file.getAbsolutePath());
			FidFile fidFile = fidFileManager.addUserFidFile(file);
			if (fidFile == null) {
				printerr("Could not attach " + file.getAbsolutePath());
				continue;
			}
			fidFile.setActive(true);
			attached++;
		}

		if (attached == 0) {
			printerr("No " + FIDB_EXTENSION + " files found in " + folder.getAbsolutePath());
			return;
		}
		println("Attached " + attached + " Function ID database(s)");

		// Re-run matching over the whole program. Running the analyzer directly
		// avoids a full re-analysis, and unlike the auto-analysis pass it also
		// revisits functions that were already named.
		println("Applying Function ID matches to " + currentProgram.getName());
		new FidAnalyzer().added(currentProgram, currentProgram.getMemory(), monitor, new MessageLog());
		println("Done");
	}
}
