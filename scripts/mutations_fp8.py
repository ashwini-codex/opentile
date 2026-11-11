# E4M3-only mutants. Each old string must appear once in the named file.
MUTANTS = [
    ("F01", "rtl/pe.sv", "assign nan_p = nan_a | nan_b;", "assign nan_p = nan_a;", "NaN from A only"),
    ("F02", "rtl/pe.sv", "assign s_p   = s_a ^ s_b;", "assign s_p   = s_a;", "drop sign XOR"),
    ("F03", "rtl/pe.sv", "assign z_p   = !nan_p && (z_a || z_b);", "assign z_p   = 1'b0;", "never classify zero"),
    ("F04", "rtl/pe.sv", "assign sig_p = sig_a * sig_b; // 4×4-bit significand multiply", "assign sig_p = sig_a * 4'd1; // 4×4-bit significand multiply", "drop B significand"),
    ("F05", "rtl/pe.sv", "assign shamt = 5'(exp_sum + 7'sd18);", "assign shamt = 5'(exp_sum + 7'sd17);", "align exp off-by-one"),
    ("F06", "rtl/pe.sv", "assign exp_a = (ua[6:3] == 4'd0) ? -6'sd9 : $signed({2'b00, ua[6:3]}) - 6'sd10;", "assign exp_a = (ua[6:3] == 4'd0) ? -6'sd8 : $signed({2'b00, ua[6:3]}) - 6'sd10;", "subnormal exp -8"),
    ("F07", "rtl/pe.sv", "            logic signed [42:0] acc_fx;", "            logic signed [39:0] acc_fx;", "40-bit acc"),
    ("F08", "rtl/pe.sv", "                    if (valid) begin", "                    if (1'b1) begin", "ignore valid"),
    ("F09", "rtl/pe.sv", "                    fp32 = CANON_NAN;", "                    fp32 = 32'd0;", "NaN to +0"),
    ("F10", "rtl/pe.sv", "                            all_neg0 <= s_p && (all_neg0 || !seen);", "                            all_neg0 <= 1'b0;", "never -0"),
    ("F11", "rtl/pe.sv", "                            bump = round_bit && (sticky || sig24[0]);", "                            bump = round_bit;", "ties up"),
    ("F12", "rtl/pe.sv", "                            acc_fx   <= acc_fx + addend;", "                            acc_fx   <= acc_fx;", "drop E4M3 MAC"),
]
