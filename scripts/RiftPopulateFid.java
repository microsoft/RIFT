// Populates a Function ID database from every program in the current Ghidra project.
// Invoked by RIFT's FunctionIdDb_Engine as a headless post-script, after a separate
// headless run has imported and analyzed the object files of one crate or toolchain.
// Usage: RiftPopulateFid.java <fidb> <family> <version> <variant> <languageId>
//@category FunctionID
import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

import ghidra.app.script.GhidraScript;
import ghidra.feature.fid.db.FidDB;
import ghidra.feature.fid.db.FidFile;
import ghidra.feature.fid.db.FidFileManager;
import ghidra.feature.fid.service.FidPopulateResult;
import ghidra.feature.fid.service.FidService;
import ghidra.framework.model.DomainFile;
import ghidra.framework.model.DomainFolder;
import ghidra.program.database.ProgramContentHandler;
import ghidra.program.model.lang.LanguageID;
import ghidra.util.exception.CancelledException;

public class RiftPopulateFid extends GhidraScript {

	// Markers RIFT greps for. analyzeHeadless exits 0 even when a script throws,
	// so the Python side cannot rely on the exit code alone.
	private static final String RESULT_MARKER = "RIFT_FID_RESULT";
	private static final String SKIP_MARKER = "RIFT_FID_SKIP";

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		if (args.length != 5) {
			throw new IllegalArgumentException(
				"Usage: RiftPopulateFid.java <fidb> <family> <version> <variant> <languageId>");
		}
		File dbFile = new File(args[0]);
		String family = args[1];
		String version = args[2];
		String variant = args[3];
		LanguageID languageId = new LanguageID(args[4]);

		FidFileManager fidFileManager = FidFileManager.getInstance();
		if (!dbFile.exists()) {
			fidFileManager.createNewFidDatabase(dbFile);
		}
		FidFile fidFile = fidFileManager.addUserFidFile(dbFile);
		if (fidFile == null) {
			throw new IOException("Could not attach FidDb " + dbFile.getAbsolutePath());
		}

		int added = populate(fidFile, family, version, variant, languageId);
		if (added < 0) {
			return; // already populated by an earlier invocation
		}
		if (added == 0) {
			// An empty database loads without error and matches nothing, which is
			// worse than no database at all. Leave nothing behind.
			fidFileManager.removeUserFile(fidFile);
			dbFile.delete();
			throw new IOException("No functions were added to " + dbFile.getAbsolutePath());
		}
	}

	/**
	 * Populates the database with one library built from all programs in the project.
	 * Returns the number of functions added, or -1 if the library already existed.
	 */
	private int populate(FidFile fidFile, String family, String version, String variant,
			LanguageID languageId) throws Exception {
		FidDB fidDb = fidFile.getFidDB(true);
		try {
			// A post-script runs once per program in the project, so every call
			// after the first one must be a no-op.
			if (!fidDb.findLibrariesByName(family, version, variant).isEmpty()) {
				println(SKIP_MARKER + " " + family + ":" + version + ":" + variant);
				return -1;
			}

			List<DomainFile> programs = new ArrayList<>();
			findPrograms(programs, getProjectRootFolder());
			if (programs.isEmpty()) {
				throw new IOException("Project contains no programs to ingest");
			}
			println("Ingesting " + programs.size() + " programs into " + family + ":" + version +
				":" + variant);

			FidService service = new FidService();
			FidPopulateResult result = service.createNewLibraryFromPrograms(fidDb, family, version,
				variant, programs, null, languageId, null, null, monitor);
			if (result == null) {
				throw new IOException("FidService returned no result");
			}

			println(RESULT_MARKER + " added=" + result.getTotalAdded() + " excluded=" +
				result.getTotalExcluded() + " attempted=" + result.getTotalAttempted());
			if (result.getTotalAdded() > 0) {
				fidDb.saveDatabase("Populated by RIFT", monitor);
			}
			return result.getTotalAdded();
		}
		finally {
			fidDb.close();
		}
	}

	/**
	 * Recursively collects every program under the given folder. Follows neither
	 * folder-links nor program-links, matching Ghidra's own CreateMultipleLibraries.
	 */
	private void findPrograms(List<DomainFile> programs, DomainFolder folder)
			throws CancelledException {
		if (folder == null) {
			return;
		}
		for (DomainFile domainFile : folder.getFiles()) {
			monitor.checkCancelled();
			if (domainFile.getContentType().equals(ProgramContentHandler.PROGRAM_CONTENT_TYPE)) {
				programs.add(domainFile);
			}
		}
		for (DomainFolder subFolder : folder.getFolders()) {
			monitor.checkCancelled();
			findPrograms(programs, subFolder);
		}
	}
}
