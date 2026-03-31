import logging
from datetime import datetime
from typing import Optional

from backend.app.modules.sapro.oid_compiler.models import OidEntry, SoapTableInfo

logger = logging.getLogger(__name__)

# Tables with known modeling logic (fully implemented)
# Maps entry_name -> handler method name
KNOWN_TABLE_HANDLERS = {
    "rsBWMNetworkEntry": "_generate_bwm_network",
}


class ModelingGenerator:
    """Generate SAPRO TCL modeling files.

    Handles two types of modeling:
    1. Hidden column computation — when CC sends partial data and firmware
       auto-computes hidden columns (e.g., rsBWMNetworkEntry FromIP/ToIP).
    2. Modify → Current table mirroring — copies rows from "Modify" config
       tables to their "Current" counterparts so CC sees active configuration.
    """

    def __init__(
        self,
        oid_entries: list[OidEntry],
        soap_tables: list[SoapTableInfo],
    ):
        self.oid_entries = oid_entries
        self.soap_tables = soap_tables

        # Build lookup: entry_name -> {col_position -> OidEntry}
        self._entry_columns: dict[str, dict[int, OidEntry]] = {}
        # Build lookup: entry_name -> entry OID
        self._entry_oids: dict[str, str] = {}
        # Modify -> Current table pairs: [(modify_entry, current_entry, rowstatus_col_oid)]
        self._mirror_pairs: list[tuple[str, str, str]] = []

        self._build_lookups()
        self._detect_mirror_pairs()

    @property
    def mirror_pairs(self) -> list[tuple[str, str, str]]:
        """Return detected Modify -> Current mirror pairs."""
        return self._mirror_pairs

    def _build_lookups(self) -> None:
        """Build mappings from entry names to their column OID entries."""
        # Group columns by table entry name
        table_columns: dict[str, list[OidEntry]] = {}
        for e in self.oid_entries:
            if e.is_table_entry:
                self._entry_oids[e.label] = e.oid
            if e.is_table_column and e.entry_name:
                table_columns.setdefault(e.entry_name, []).append(e)

        # For each table, sort columns by OID and assign positions
        for entry_name, cols in table_columns.items():
            cols.sort(key=lambda c: [int(x) for x in c.oid.split(".")])
            self._entry_columns[entry_name] = {
                i: col for i, col in enumerate(cols, start=1)
            }

    def _detect_mirror_pairs(self) -> None:
        """Find Modify -> Current table pairs by naming convention.

        Current tables have 'Current' in their entry name and mirror a
        corresponding Modify table. The RowStatus column in the Modify
        table is identified so mirroring can skip it (Current tables
        don't have RowStatus).
        """
        for current_name, current_oid in self._entry_oids.items():
            if "Current" not in current_name:
                continue
            # Derive modify table name: rsBWMCurrentNetworkEntry -> rsBWMNetworkEntry
            modify_name = current_name.replace("Current", "")
            # Special case: rsBWMMacGroupCurrentEntry -> rsBWMMacGroupEntry
            if modify_name not in self._entry_oids and "Current" in current_name:
                # Try suffix pattern: XxxCurrentYyy -> XxxYyy
                parts = current_name.split("Current")
                if len(parts) == 2:
                    modify_name = parts[0] + parts[1]

            if modify_name not in self._entry_oids:
                continue
            if modify_name not in self._entry_columns:
                continue

            # Find the RowStatus column OID in the Modify table
            rowstatus_oid = ""
            for pos, col in self._entry_columns[modify_name].items():
                if "Status" in col.label and col.syntax == "Integer":
                    # Check if it looks like RowStatus (enum values 1-6)
                    if col.has_enum and "active" in col.enum_values:
                        rowstatus_oid = col.oid
                        break
                    # Fallback: any Integer column with "Status" in name
                    if not rowstatus_oid:
                        rowstatus_oid = col.oid

            self._mirror_pairs.append((modify_name, current_name, rowstatus_oid))

        logger.info(f"Detected {len(self._mirror_pairs)} Modify->Current table mirror pairs")

    def _get_column_oid(self, entry_name: str, position: int) -> Optional[str]:
        """Get the full OID for a column by entry name and position."""
        cols = self._entry_columns.get(entry_name, {})
        col = cols.get(position)
        return col.oid if col else None

    def _get_column_label(self, entry_name: str, position: int) -> Optional[str]:
        """Get the SNMP label for a column by entry name and position."""
        cols = self._entry_columns.get(entry_name, {})
        col = cols.get(position)
        return col.label if col else None

    def _get_column_syntax(self, entry_name: str, position: int) -> Optional[str]:
        """Get the SNMP syntax for a column by entry name and position."""
        cols = self._entry_columns.get(entry_name, {})
        col = cols.get(position)
        return col.syntax if col else None

    def generate(self) -> str:
        """Generate the complete TCL modeling file content."""
        lines: list[str] = []

        lines.append(self._generate_header())
        lines.append(self._generate_init_action())

        # Generate action blocks for tables with hidden columns
        tables_with_hidden = [
            t for t in self.soap_tables
            if t.hidden_count > 0 and t.entry_name in self._entry_columns
        ]

        for table in tables_with_hidden:
            handler_name = KNOWN_TABLE_HANDLERS.get(table.entry_name)
            if handler_name:
                handler = getattr(self, handler_name)
                block = handler(table)
                if block:
                    lines.append(block)
            else:
                skeleton = self._generate_skeleton(table)
                if skeleton:
                    lines.append(skeleton)

        # TODO: Modify -> Current table mirroring disabled until we find
        # a trigger strategy that doesn't conflict with computation blocks.
        # The entry-level OID prefix match causes both computation and
        # mirror blocks to fire on the same Set event.

        # Summary of tables analyzed
        lines.append(self._generate_summary(tables_with_hidden))

        content = "\n".join(lines) + "\n"
        logger.info(
            f"Generated modeling file: "
            f"{len(tables_with_hidden)} tables, "
            f"{sum(1 for t in tables_with_hidden if t.entry_name in KNOWN_TABLE_HANDLERS)} fully implemented, "
            f"{len(self._mirror_pairs)} mirror pairs"
        )
        return content

    def _generate_header(self) -> str:
        """Generate the file header comment block."""
        date = datetime.now().strftime("%a %b %d %H:%M:%S %Y")
        return f"""\
# ===================================================================
# DefensePro TCL Modeling File
# Generated by SimulatorTools MIB Compiler
# Date: {date}
#
# This file simulates DefensePro firmware behavior for SNMP Set
# operations on tables with hidden (firmware-computed) columns.
#
# When CyberController sends a Set with only visible columns,
# these scripts auto-compute the hidden column values so the
# simulator behaves like a real DefensePro device.
#
# SAPRO Actions used:
#   %init_action             - Runs at device startup (utility procs)
#   %after_set_action <oid>  - Runs after a Set on matching OID
#
# SAPRO TCL commands used:
#   SA_getreqvb   - Get current Set varbind (oid, type, value)
#   SA_getvar     - Get variable values from the MIB store
#   SA_setvar     - Set variable values in the MIB store
#   SA_getmyip    - Get this device's IP address
#   SA_puts       - Debug output
# ==================================================================="""

    def _generate_init_action(self) -> str:
        """Generate %init_action with reusable utility procedures."""
        return """\

%init_action
    # ---------------------------------------------------------------
    # Device initialization and reusable utility procedures
    # ---------------------------------------------------------------

    set myIP [SA_getmyip]
    SA_settcldebugflag 1
    SA_settcldebugfile tcl_${myIP}.dbg
    SA_puts "\\n=== sim_v2.tcl init_action started for $myIP ==="

    # -----------------------------------------------------------
    # switch_column_oid: Replace the column OID prefix in a full
    # varbind OID, preserving the instance suffix.
    #
    # When SAPRO triggers %after_set_action for a column, the
    # varbind OID has the form:
    #   <entry_oid>.<source_col>.<instance_suffix>
    #
    # This proc swaps <source_col> for <target_col> so we can
    # read or write a different column in the same row.
    #
    # Arguments:
    #   vb_oid         - Full OID from the varbind
    #   source_col_oid - Column OID prefix being replaced
    #                    (e.g., "1.3.6.1.4.1.89.35.1.60.63.1.3")
    #   target_col_oid - Column OID prefix to substitute
    #                    (e.g., "1.3.6.1.4.1.89.35.1.60.63.1.5")
    #
    # Returns: New OID with column swapped, instance preserved
    # -----------------------------------------------------------
    proc switch_column_oid {vb_oid source_col_oid target_col_oid} {
        set instance [string range $vb_oid [string length $source_col_oid] end]
        set new_oid "${target_col_oid}${instance}"
        SA_puts "\\n  switch_column_oid: $source_col_oid -> $target_col_oid instance=$instance result=$new_oid"
        return $new_oid
    }

    # -----------------------------------------------------------
    # copy_column_value: Copy the current Set varbind's value to
    # another column in the same row. Swaps the OID prefix and
    # passes just the new OID to SA_setvar — SAPRO copies the
    # type and value from the current Set request automatically.
    # This matches the pattern from the working test_snmp.tcl.
    #
    # Arguments:
    #   varbind        - The Set varbind from SA_getreqvb
    #   source_col_oid - Column OID prefix of the source
    #   target_col_oid - Column OID prefix of the target
    # -----------------------------------------------------------
    proc copy_column_value {varbind source_col_oid target_col_oid} {
        SA_puts "\\n  copy_column_value: raw varbind=$varbind"
        set curvb [lindex $varbind 0]
        SA_puts "\\n  copy_column_value: curvb=$curvb"
        set src_oid [lindex $curvb 0]
        set src_type [lindex $curvb 1]
        set src_value [lindex $curvb 2]
        SA_puts "\\n  copy_column_value: src_oid=$src_oid src_type=$src_type src_value=$src_value"
        set target_oid [switch_column_oid $src_oid $source_col_oid $target_col_oid]
        SA_puts "\\n  copy_column_value: SA_setvar target_oid=$target_oid type=$src_type value=$src_value"
        SA_setvar [list [list $target_oid $src_type $src_value]]
    }

    # -----------------------------------------------------------
    # get_column_value: Read the current value of a column in the
    # same row. Returns the raw value (third space-separated
    # element from SA_getvar result).
    #
    # Arguments:
    #   vb_oid         - Full OID from the triggering varbind
    #   source_col_oid - Column OID prefix of the triggering column
    #   target_col_oid - Column OID prefix of the column to read
    #
    # Returns: The raw value string
    # -----------------------------------------------------------
    proc get_column_value {vb_oid source_col_oid target_col_oid} {
        set target_oid [switch_column_oid $vb_oid $source_col_oid $target_col_oid]
        SA_puts "\\n  get_column_value: SA_getvar target_oid=$target_oid"
        set result [SA_getvar [list $target_oid]]
        SA_puts "\\n  get_column_value: raw result=$result"
        set curvb [lindex $result 0]
        SA_puts "\\n  get_column_value: curvb=$curvb"
        set val [lindex $curvb 2]
        SA_puts "\\n  get_column_value: returning value=$val"
        return $val
    }

    # -----------------------------------------------------------
    # set_column_value: Write a value to a column in the same row
    # as a given varbind.
    #
    # Arguments:
    #   vb_oid         - Full OID from the triggering varbind
    #   source_col_oid - Column OID prefix of the triggering column
    #   target_col_oid - Column OID prefix of the column to write
    #   type           - SNMP type (e.g., "Integer", "OctetString")
    #   value          - The value to set
    # -----------------------------------------------------------
    proc set_column_value {vb_oid source_col_oid target_col_oid type value} {
        set target_oid [switch_column_oid $vb_oid $source_col_oid $target_col_oid]
        SA_puts "\\n  set_column_value: SA_setvar oid=$target_oid type=$type value=$value"
        SA_setvar [list [list $target_oid $type $value]]
    }

    # -----------------------------------------------------------
    # hex_to_ipv4: Convert a hex string to dotted-decimal IPv4.
    # Handles IPv4-mapped IPv6 format used by DefensePro
    # (e.g., 0x00000000000000000000ffff0a010101 -> 10.1.1.1)
    #
    # Arguments:
    #   hex_string - Hex value (with or without 0x prefix)
    #
    # Returns: IPv4 address in dotted-decimal notation
    # -----------------------------------------------------------
    proc hex_to_ipv4 {hex_string} {
        set hex_string [string trimleft $hex_string "0x"]
        # Take last 8 hex digits (4 bytes) for IPv4
        set hex_string [string range $hex_string end-7 end]
        set hex_string [format "%08s" $hex_string]

        set octet1 [expr 0x[string range $hex_string 0 1]]
        set octet2 [expr 0x[string range $hex_string 2 3]]
        set octet3 [expr 0x[string range $hex_string 4 5]]
        set octet4 [expr 0x[string range $hex_string 6 7]]

        return "$octet1.$octet2.$octet3.$octet4"
    }

    # -----------------------------------------------------------
    # ipv4_to_hex: Convert dotted-decimal IPv4 to DefensePro hex
    # format (IPv4-mapped IPv6: 0x00000000000000000000ffffXXXXXXXX)
    #
    # Arguments:
    #   ip_address - IPv4 in dotted-decimal (e.g., "10.1.1.1")
    #
    # Returns: Hex string in IPv4-mapped IPv6 format
    # -----------------------------------------------------------
    proc ipv4_to_hex {ip_address} {
        set octets [split $ip_address "."]
        set ipv4_hex ""
        foreach octet $octets {
            append ipv4_hex [format "%02x" $octet]
        }
        return "0x00000000000000000000ffff$ipv4_hex"
    }

    # -----------------------------------------------------------
    # compute_broadcast: Calculate the broadcast address from a
    # network address and subnet mask.
    #
    # broadcast = network_ip | (~subnet_mask & 0xFFFFFFFF)
    #
    # Arguments:
    #   network_ip  - Network IP in dotted-decimal
    #   subnet_mask - Subnet mask in dotted-decimal
    #
    # Returns: Broadcast address in dotted-decimal
    # -----------------------------------------------------------
    proc compute_broadcast {network_ip subnet_mask} {
        # Convert IP to 32-bit integer
        proc _ip_to_int {ip} {
            set result 0
            foreach octet [split $ip "."] {
                set result [expr {($result << 8) + $octet}]
            }
            return $result
        }

        # Convert 32-bit integer to IP
        proc _int_to_ip {int_val} {
            return "[expr {($int_val >> 24) & 0xFF}].[expr {($int_val >> 16) & 0xFF}].[expr {($int_val >> 8) & 0xFF}].[expr {$int_val & 0xFF}]"
        }

        set net_int [_ip_to_int $network_ip]
        set mask_int [_ip_to_int $subnet_mask]
        set broadcast_int [expr {$net_int | (~$mask_int & 0xFFFFFFFF)}]
        return [_int_to_ip $broadcast_int]
    }

    # -----------------------------------------------------------
    # decode_string_instance: Parse a string-indexed table instance
    # suffix to extract the name string and subindex.
    #
    # Instance format: .<length>.<ascii_bytes...>.<subindex>
    # Example: .5.116.101.115.116.50.0 = "test2", subindex 0
    #
    # Arguments:
    #   instance  - The instance suffix (e.g., ".5.116.101.115.116.50.0")
    #
    # Returns: list of {name subindex}
    # -----------------------------------------------------------
    proc decode_string_instance {instance} {
        # Remove leading dot
        set parts [split [string range $instance 1 end] "."]
        SA_puts "\\n  decode_string_instance: parts=$parts"
        set name_len [lindex $parts 0]
        set name_str ""
        for {set i 1} {$i <= $name_len} {incr i} {
            set ascii_val [lindex $parts $i]
            append name_str [format "%c" $ascii_val]
        }
        set subindex [lindex $parts [expr {$name_len + 1}]]
        SA_puts "\\n  decode_string_instance: name=$name_str subindex=$subindex"
        return [list $name_str $subindex]
    }

    # -----------------------------------------------------------
    # mirror_to_current: Copy a Set varbind from a Modify table
    # to its corresponding Current table.
    #
    # DefensePro has paired tables: "Modify" tables hold candidate
    # config, "Current" tables hold active config. When CC writes
    # to a Modify table, this proc mirrors the value to Current
    # so CC sees it as active configuration.
    #
    # The OID translation is simple: replace the Modify entry OID
    # prefix with the Current entry OID prefix. The column number
    # and instance suffix stay the same.
    #
    # Arguments:
    #   varbind          - The Set varbind list {oid type value}
    #   modify_entry_oid - Entry OID of the Modify table
    #   current_entry_oid - Entry OID of the Current table
    # -----------------------------------------------------------
    proc mirror_to_current {varbind modify_entry_oid current_entry_oid} {
        SA_puts "\\n  mirror_to_current: raw varbind=$varbind"
        set curvb [lindex $varbind 0]
        set vb_oid [lindex $curvb 0]
        set vb_type [lindex $curvb 1]
        set vb_value [lindex $curvb 2]
        set suffix [string range $vb_oid [string length $modify_entry_oid] end]
        set target_oid "${current_entry_oid}${suffix}"
        SA_puts "\\n  mirror_to_current: src=$vb_oid -> target=$target_oid type=$vb_type value=$vb_value"
        SA_setvar [list [list $target_oid $vb_type $vb_value]]
    }"""

    def _generate_bwm_network(self, table: SoapTableInfo) -> str:
        """Generate modeling for rsBWMNetworkEntry.

        When CC creates a BWM Network, it sets:
          - C1: Name (key)
          - C2: SubIndex (key)
          - C3: Address (visible)
          - C4: Mask (visible)

        Firmware auto-computes:
          - C5: FromIP = copy of Address
          - C6: ToIP = broadcast(Address, Mask)
          - C7: Mode = 1 (ipMask) — default when Address+Mask are provided
          - C8: Status = RowStatus (handled by SAPRO %dcol, no TCL needed)

        Also mirrors the computed values to rsBWMCurrentNetworkEntry.
        """
        modify_entry = "rsBWMNetworkEntry"
        current_entry = "rsBWMCurrentNetworkEntry"
        entry_oid = self._entry_oids.get(modify_entry)
        current_oid = self._entry_oids.get(current_entry)
        if not entry_oid:
            logger.warning("rsBWMNetworkEntry not found in OID entries")
            return ""

        # Get column OIDs from Modify table
        address_oid = self._get_column_oid(modify_entry, 3)
        mask_oid = self._get_column_oid(modify_entry, 4)
        from_ip_oid = self._get_column_oid(modify_entry, 5)
        to_ip_oid = self._get_column_oid(modify_entry, 6)
        mode_oid = self._get_column_oid(modify_entry, 7)

        if not all([address_oid, mask_oid, from_ip_oid, to_ip_oid, mode_oid]):
            logger.warning("rsBWMNetworkEntry: could not resolve all column OIDs")
            return ""

        address_label = self._get_column_label(modify_entry, 3)
        from_ip_label = self._get_column_label(modify_entry, 5)
        to_ip_label = self._get_column_label(modify_entry, 6)
        mode_label = self._get_column_label(modify_entry, 7)

        # Build mirror lines for ALL columns to Current table
        mirror_lines = ""
        if current_oid:
            # Mirror each column: read from Modify, write to Current
            # For columns CC just set (Address, Mask, Mode), SA_getvar reads them.
            # For computed columns (FromIP, ToIP), we already have the values.
            mirror_lines = f"""
    # Mirror data columns (C3-C7) to Current table ({current_entry})
    # Skip index columns C1 (Name) and C2 (SubIndex) — SAPRO handles
    # those from the OID instance when the row is created.
    set instance [string range $vb_oid [string length "{address_oid}"] end]
    SA_puts "\\n  mirror instance suffix: $instance"
    foreach col_suffix {{.3 .4 .5 .6 .7}} {{
        set full_modify_oid "{entry_oid}${{col_suffix}}${{instance}}"
        SA_puts "\\n  mirror: reading $full_modify_oid"
        set getresult [SA_getvar [list $full_modify_oid]]
        SA_puts "\\n  mirror: SA_getvar raw result=$getresult"
        set curvb [lindex $getresult 0]
        set col_type [lindex $curvb 1]
        set col_value [lindex $curvb 2]
        set full_current_oid "{current_oid}${{col_suffix}}${{instance}}"
        SA_puts "\\n  mirror: writing $full_current_oid type=$col_type value=$col_value"
        SA_setvar [list [list $full_current_oid $col_type $col_value]]
    }}"""

        return f"""\

# ===================================================================
# rsBWMNetworkEntry — BWM Network Classes
# Entry OID: {entry_oid}
#
# Visible columns (set by CC):
#   C3: {address_label} (Address)
#   C4: {self._get_column_label(modify_entry, 4)} (Mask)
#
# Hidden columns (computed by this script):
#   C5: {from_ip_label} = copy of Address
#   C6: {to_ip_label}   = broadcast(Address, Mask)
#   C7: {mode_label}    = 1 (ipMask mode, default for Address+Mask)
#   C8: Status           = RowStatus (handled by SAPRO %dcol)
#
# All columns are also mirrored to {current_entry}.
# ===================================================================
%after_set_action {address_oid}
    SA_puts "\\n=== after_set_action FIRED for {address_oid} ==="
    set varbind [SA_getreqvb]
    SA_puts "\\n  raw SA_getreqvb result: $varbind"
    set curvb [lindex $varbind 0]
    SA_puts "\\n  curvb (lindex 0): $curvb"
    set vb_oid [lindex $curvb 0]
    set vb_type [lindex $curvb 1]
    set address_hex [lindex $curvb 2]
    SA_puts "\\n  vb_oid=$vb_oid vb_type=$vb_type address_hex=$address_hex"
    set to_ip_hex ""

    # C5 (FromIP) = copy of Address
    SA_puts "\\n--- Step 1: Copy Address to FromIP ---"
    copy_column_value $varbind "{address_oid}" "{from_ip_oid}"

    # Read the Mask value from C4 to compute ToIP
    SA_puts "\\n--- Step 2: Read Mask from C4 ---"
    set mask_hex [get_column_value $vb_oid "{address_oid}" "{mask_oid}"]
    SA_puts "\\n  mask_hex before trimright: '$mask_hex'"
    set mask_hex [string trimright $mask_hex]
    SA_puts "\\n  mask_hex after trimright: '$mask_hex'"

    # C6 (ToIP) = broadcast(Address, Mask)
    SA_puts "\\n--- Step 3: Compute ToIP (broadcast) ---"
    if {{$mask_hex ne "" && $mask_hex ne "0.0.0.0"}} {{
        set from_ip [hex_to_ipv4 $address_hex]
        SA_puts "\\n  from_ip (dotted): $from_ip"
        SA_puts "\\n  mask (already dotted): $mask_hex"
        set broadcast [compute_broadcast $from_ip $mask_hex]
        SA_puts "\\n  broadcast: $broadcast"
        set to_ip_hex [ipv4_to_hex $broadcast]
        SA_puts "\\n  to_ip_hex: $to_ip_hex"
        set_column_value $vb_oid "{address_oid}" "{to_ip_oid}" "OctetString" $to_ip_hex
    }} else {{
        SA_puts "\\n  SKIPPED: mask is empty or 0.0.0.0"
    }}

    # C7 (Mode) = 1 (ipMask)
    SA_puts "\\n--- Step 4: Set Mode to 1 ---"
    set_column_value $vb_oid "{address_oid}" "{mode_oid}" "Integer" 1

    SA_puts "\\n--- Step 5: Mirror to Current table ---"
{mirror_lines}
    SA_puts "\\n=== after_set_action COMPLETE ==="
"""

    def _generate_mirror_block(
        self, modify_name: str, current_name: str, rowstatus_oid: str
    ) -> str:
        """Generate a %after_set_action block that mirrors Modify -> Current table.

        When CC writes to any column in the Modify table, the value is
        immediately copied to the same column in the Current table.
        RowStatus columns are skipped (Current tables don't have them).
        """
        modify_oid = self._entry_oids.get(modify_name)
        current_oid = self._entry_oids.get(current_name)

        if not modify_oid or not current_oid:
            logger.warning(
                f"Cannot generate mirror for {modify_name} -> {current_name}: "
                f"missing entry OID"
            )
            return ""

        # Build the RowStatus skip condition
        if rowstatus_oid:
            skip_check = f"""
    # Skip RowStatus column — Current tables don't have it
    if {{[string match "{rowstatus_oid}*" $vb_oid]}} {{
        return
    }}
"""
        else:
            skip_check = ""

        return f"""\

# -------------------------------------------------------------------
# {modify_name} -> {current_name}
# Mirror every Set on the Modify table to the Current (active) table.
# -------------------------------------------------------------------
%after_set_action {modify_oid}
    set varbind [SA_getreqvb]
    set vb_oid [lindex $varbind 0]
{skip_check}\
    mirror_to_current $varbind "{modify_oid}" "{current_oid}" """

    def _classify_hidden_column(self, entry_name: str, col) -> str:
        """Classify a hidden column's type.

        Returns one of: 'rowstatus', 'default', 'computed', 'unknown'
        """
        label = self._get_column_label(entry_name, col.position) or ""
        syntax = self._get_column_syntax(entry_name, col.position) or ""

        # RowStatus columns (Integer with "Status" in name and enum 1-6)
        if "Status" in label and syntax == "Integer":
            return "rowstatus"

        # All other hidden columns in tables WITHOUT known computation logic
        # are treated as default-value columns. The %dcol in the VAR file
        # provides the default; no TCL is needed.
        return "default"

    def _generate_skeleton(self, table: SoapTableInfo) -> str:
        """Generate documentation for tables with hidden columns.

        Categorizes hidden columns and documents whether TCL is needed.
        Tables where all hidden columns are RowStatus or defaults get
        a documentation-only comment block (no skeleton code).
        """
        entry_name = table.entry_name
        entry_oid = self._entry_oids.get(entry_name, "<unknown>")

        # Skip entirely-hidden tables (internal, no CC interaction)
        if table.visible_count == 0:
            return ""

        # Skip tables without create capability (read-only mirrors)
        if not table.has_create:
            return ""

        hidden_cols = [c for c in table.columns if c.is_hidden]

        # Classify each hidden column
        classifications = {}
        for c in hidden_cols:
            classifications[c.position] = self._classify_hidden_column(entry_name, c)

        # If all hidden columns are RowStatus or defaults, no TCL needed
        needs_tcl = any(
            cls not in ("rowstatus", "default")
            for cls in classifications.values()
        )
        if needs_tcl:
            return self._generate_skeleton_with_code(table, classifications)

        # Documentation-only: explain why no TCL is needed
        hidden_lines = []
        for c in hidden_cols:
            label = self._get_column_label(entry_name, c.position) or f"<C{c.position}>"
            syntax = self._get_column_syntax(entry_name, c.position) or "?"
            cls = classifications[c.position]
            tag = "[RowStatus]" if cls == "rowstatus" else "[default from %dcol]"
            hidden_lines.append(f"#   C{c.position}: {label} ({syntax}) — {tag}")

        hidden_block = "\n".join(hidden_lines)

        return f"""
# ===================================================================
# {entry_name} — NO TCL NEEDED
# Entry OID: {entry_oid}
# Namespace: {table.soap_namespace or "unknown"}
# {table.visible_count} visible, {table.hidden_count} hidden columns
#
# Hidden columns are all handled by SAPRO's %dcol defaults:
{hidden_block}
#
# RowStatus columns are managed by SAPRO's rowstatus(1) value type.
# Default-value columns get their initial values from %dcol in the
# VAR file. CC does not read these hidden columns.
# ==================================================================="""

    def _generate_skeleton_with_code(
        self, table: SoapTableInfo, classifications: dict[int, str]
    ) -> str:
        """Generate a commented skeleton for tables that may need TCL."""
        entry_name = table.entry_name
        entry_oid = self._entry_oids.get(entry_name, "<unknown>")
        hidden_cols = [c for c in table.columns if c.is_hidden]
        visible_cols = [c for c in table.columns if not c.is_hidden]

        visible_lines = []
        for c in visible_cols:
            label = self._get_column_label(entry_name, c.position) or f"<C{c.position}>"
            key_marker = " (key)" if c.is_key else ""
            visible_lines.append(f"#   C{c.position}: {label} — SOAP: {c.soap_name}{key_marker}")

        hidden_lines = []
        for c in hidden_cols:
            label = self._get_column_label(entry_name, c.position) or f"<C{c.position}>"
            syntax = self._get_column_syntax(entry_name, c.position) or "?"
            col_oid = self._get_column_oid(entry_name, c.position) or "?"
            cls = classifications[c.position]
            hidden_lines.append(f"#   C{c.position}: {label} ({syntax}) — OID: {col_oid} [{cls}]")

        trigger_candidates = [c for c in visible_cols if not c.is_key]
        if not trigger_candidates:
            trigger_candidates = visible_cols
        if trigger_candidates:
            trigger_col = trigger_candidates[0]
            trigger_oid = self._get_column_oid(entry_name, trigger_col.position) or "<trigger_oid>"
            trigger_label = self._get_column_label(entry_name, trigger_col.position) or "?"
        else:
            trigger_oid = "<trigger_oid>"
            trigger_label = "<first_visible_column>"

        visible_block = "\n".join(visible_lines)
        hidden_block = "\n".join(hidden_lines)

        return f"""
# ===================================================================
# {entry_name} — SKELETON (needs Phase 3 investigation)
# Entry OID: {entry_oid}
# Namespace: {table.soap_namespace or "unknown"}
# {table.visible_count} visible, {table.hidden_count} hidden columns
#
# Visible columns (set by CC):
{visible_block}
#
# Hidden columns:
{hidden_block}
#
# TODO: Capture real device behavior to determine if any hidden
#       columns need computation logic beyond %dcol defaults.
# ===================================================================
# %after_set_action {trigger_oid}
#     # Triggered when {trigger_label} is set
#     set varbind [SA_getreqvb]
#     set vb_oid [lindex $varbind 0]
#
#     # TODO: Implement hidden column logic here
#     # Example: copy_column_value $varbind "{trigger_oid}" "<target_col_oid>"
#     # Example: set_column_value $vb_oid "{trigger_oid}" "<target_col_oid>" "Integer" 1"""

    def _generate_summary(self, tables_with_hidden: list[SoapTableInfo]) -> str:
        """Generate a summary comment block at the end of the file."""
        implemented = []
        no_tcl = []
        skeleton = []

        for t in tables_with_hidden:
            if t.entry_name in KNOWN_TABLE_HANDLERS:
                implemented.append(t.entry_name)
                continue
            if t.visible_count == 0 or not t.has_create:
                continue

            hidden_cols = [c for c in t.columns if c.is_hidden]
            classifications = {
                c.position: self._classify_hidden_column(t.entry_name, c)
                for c in hidden_cols
            }
            needs_tcl = any(
                cls not in ("rowstatus", "default")
                for cls in classifications.values()
            )
            if needs_tcl:
                skeleton.append(t.entry_name)
            else:
                no_tcl.append(t.entry_name)

        impl_list = "\n".join(f"#   - {n}" for n in implemented) or "#   (none)"
        notcl_list = "\n".join(f"#   - {n}" for n in no_tcl) or "#   (none)"
        skel_list = "\n".join(f"#   - {n}" for n in skeleton) or "#   (none)"
        mirror_list = "\n".join(
            f"#   - {m} -> {c}" for m, c, _ in self._mirror_pairs
        ) or "#   (none)"

        return f"""
# ===================================================================
# MODELING FILE SUMMARY
#
# Fully implemented (TCL computation logic):
{impl_list}
#
# Modify -> Current table mirroring:
{mirror_list}
#
# No TCL needed (RowStatus + defaults handled by %dcol):
{notcl_list}
#
# Needs investigation (may need TCL after Phase 3 analysis):
{skel_list}
# ==================================================================="""
