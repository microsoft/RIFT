import re

# error case: invalid version
RE_INVALID_VER = r"error\: failed to select a version for the requirement \`(.*) \= (.*)\`"
# error case: invalid version for required package
RE_INVALID_VER_REQ_P = r".*error\: failed to select a version for \`(.*)\`.*"
# error case: package needs to be downgraded
RE_SUGG_DOWNGRADE = r"cargo update -p (.*)@(.*) --precise ver"
# error: package `ring v0.17.14` cannot be built because it requires rustc 1.66.0 or newer, while the currently active rustc version is 1.63.0
RE_SUGG_DOWNGRADE2 = r"error: package `(.*)\sv(.*)` cannot be built because it requires rustc.*"
# error case: invalid crate
RE_INVALID_CRATE = r".*TOML parse error at line (\d+),.{1,100}"
RE_SYNTAX_ERR_CRATE = r"error: expected.*"
# error case: crate not found
RE_NO_MATCHING_PACKAGE = r"error: no matching package named `(.*)` found"
# error case: Wrong edition is set
# see https://doc.rust-lang.org/edition-guide/editions/
RE_WRONG_EDITION = r"\s+The package requires the Cargo feature called `(.{1,100})`, but that feature is not stabilized in this version of Cargo"
# error case: Wrong edition is set
RE_WRONG_EDITION2 = r"\s+this version of Cargo is older than the `(.{1,100})` edition"
# error case: There are multiple versions of a package
RE_MULTI_PKG_VERSIONS = r"error: There are multiple `(.*)` packages in your project, and the specification `(.*)` is ambiguous.*"

class ErrorParser():

    def __init__(self, logger):
        self.logger = logger
    
    def parse_error_msg(self, msg):
        """Parses an error message and returns dictionary with extracted information."""
        retval = {"error": "UNKNOWN_ERROR", "entity": None, "entity_meta": None}
        lines = msg.split("\n")
        i = 0
        while i < len(lines):

            line = lines[i]
            # error 1: invalid version
            m = re.match(RE_INVALID_VER, line) 
            if m:
                retval["error"] = "INVALID_VERSION"
                retval["entity"] = m.group(1)
                retval["entity_meta"] = m.group(2)
                break

            # error 2: invalid version for requirement package
            m = re.match(RE_INVALID_VER_REQ_P, line)
            if m:
                retval["error"] = "INVALID_VERSION_FOR_REQ_P"
                retval["entity"] = m.group(1)
                break

            # error 3: version of package is too high for rust version
            m = re.match(RE_SUGG_DOWNGRADE, line)
            if m:
                retval["error"] = "VERSION_TOO_HIGH"
                retval["entity"] = m.group(1)
                retval["entity_meta"] = m.group(2)
                break
            m = re.match(RE_SUGG_DOWNGRADE2, line)
            if m:
                retval["error"] = "VERSION_TOO_HIGH"
                retval["entity"] = m.group(1)
                retval["entity_meta"] = m.group(2)
                break

            # error 4: invalid crate
            m = re.match(RE_INVALID_CRATE, line)
            if m:
                retval["error"] = "INVALID_CRATE"
                retval["entity"] = m.group(1)
                break
            
            # error 5: syntax error in Config.toml, remove that specific line
            m = re.match(RE_SYNTAX_ERR_CRATE, line)
            if m:
                retval["error"] = "SYNTAX_ERROR_CRATE"
                line = lines[i+1]
                m = re.match(r".*Cargo.toml:(\d+):.{1,100}", line)
                if m:
                    self.logger.info(f"Syntax error, found removing line_num = {m.group(1)}")
                    retval["entity"] = m.group(1)
                    break

            # error 5: package not found
            m = re.match(RE_NO_MATCHING_PACKAGE, line)
            if m:
                retval["error"] = "NO_MATCHING_PACKAGE"
                retval["entity"] = m.group(1)
                break
            
            # error 6: edition features not supported
            m = re.match(RE_WRONG_EDITION, line)
            if m:
                retval["error"] = "WRONG_EDITION"
                retval["entity"] = m.group(1)
                break

            # error 7: Wrong edition
            m = re.match(RE_WRONG_EDITION2, line)
            if m:
                retval["error"] = "WRONG_EDITION2"
                retval["entity"] = m.group(1)
                break

            # error 8: Multiple versions of a package found
            m = re.match(RE_MULTI_PKG_VERSIONS, line)
            if m:
                retval["error"] = "MULTI_PKG_VERSIONS"
                retval["entity"] = m.group(1)
                break

            i += 1
        return retval 