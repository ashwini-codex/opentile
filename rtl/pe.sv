// Output-stationary PE. FMT="INT8" (default) or "E4M3".
// clr > en > hold. No rst_n; clr is datapath reset.
// valid: delayed with A. INT8 MAC ignores it. E4M3 MAC is en && valid
// so COMPUTE padding zeros are not K-products (signed-zero rule).
`default_nettype none

module pe #(
    parameter [31:0] FMT    = "INT8",
    parameter bit    TIE_UP = 1'b0
) (
    input  logic               clk,
    input  logic               clr,
    input  logic               en,
    input  logic               valid,
    input  logic signed [7:0]  a_in,
    input  logic signed [7:0]  b_in,
    output logic signed [7:0]  a_out,
    output logic signed [7:0]  b_out,
    output logic               valid_o,
    output logic signed [31:0] acc
);
    localparam bit IS_E4M3 = (FMT == "E4M3");
    localparam logic [31:0] CANON_NAN = 32'h7FC00000;
    localparam logic [31:0] FP32_NEG0 = 32'h80000000;

    generate
        if (!IS_E4M3) begin : g_int8
            logic signed [15:0] prod;
            assign prod = a_in * b_in;

            always_ff @(posedge clk) begin
                if (clr) begin
                    acc   <= 32'sd0;
                    a_out <= 8'sd0;
                    b_out <= 8'sd0;
                    valid_o <= 1'b0;
                end else if (en) begin
                    acc   <= acc + 32'(prod);
                    a_out <= a_in;
                    b_out <= b_in;
                    valid_o <= valid;
                end
            end
        end else begin : g_e4m3
            logic        poison, all_neg0, seen;
            logic signed [42:0] acc_fx;
            logic [31:0] fp32;

            logic [7:0] ua, ub;
            logic nan_a, nan_b, z_a, z_b, s_a, s_b;
            logic [3:0] sig_a, sig_b;
            logic signed [5:0] exp_a, exp_b;
            logic nan_p, z_p, s_p;
            logic [7:0] sig_p;
            logic signed [6:0] exp_sum;
            logic [4:0] shamt;
            logic [42:0] mag_u;
            logic signed [42:0] addend;

            assign ua = a_in[7:0];
            assign ub = b_in[7:0];
            assign s_a = ua[7];
            assign s_b = ub[7];
            assign nan_a = (ua[6:3] == 4'd15) && (ua[2:0] == 3'd7);
            assign nan_b = (ub[6:3] == 4'd15) && (ub[2:0] == 3'd7);
            assign z_a = (ua[6:0] == 7'd0);
            assign z_b = (ub[6:0] == 7'd0);
            assign sig_a = (ua[6:3] == 4'd0) ? {1'b0, ua[2:0]} : {1'b1, ua[2:0]};
            assign sig_b = (ub[6:3] == 4'd0) ? {1'b0, ub[2:0]} : {1'b1, ub[2:0]};
            assign exp_a = (ua[6:3] == 4'd0) ? -6'sd9 : $signed({2'b00, ua[6:3]}) - 6'sd10;
            assign exp_b = (ub[6:3] == 4'd0) ? -6'sd9 : $signed({2'b00, ub[6:3]}) - 6'sd10;

            assign nan_p = nan_a | nan_b;
            assign s_p   = s_a ^ s_b;
            assign z_p   = !nan_p && (z_a || z_b);
            assign sig_p = sig_a * sig_b; // 4×4-bit significand multiply
            assign exp_sum = exp_a + exp_b;
            assign shamt = 5'(exp_sum + 7'sd18);
            assign mag_u = {35'b0, sig_p} << shamt;
            assign addend = s_p ? -$signed(mag_u) : $signed(mag_u);

            always_ff @(posedge clk) begin
                if (clr == 1'b1) begin
                    acc_fx   <= 43'sd0;
                    poison   <= 1'b0;
                    all_neg0 <= 1'b0;
                    seen     <= 1'b0;
                    a_out    <= 8'sb0;
                    b_out    <= 8'sb0;
                    valid_o  <= 1'b0;
                end else if (en == 1'b1) begin
                    a_out   <= 8'(a_in);
                    b_out   <= 8'(b_in);
                    valid_o <= valid;
                    if (valid) begin
                        if (nan_p) begin
                            poison <= 1'b1;
                            seen   <= 1'b1;
                        end else if (z_p) begin
                            seen     <= 1'b1;
                            all_neg0 <= s_p && (all_neg0 || !seen);
                        end else begin
                            seen     <= 1'b1;
                            all_neg0 <= 1'b0;
                            acc_fx   <= acc_fx + addend;
                        end
                    end
                end
            end

            // One RNE of the exact 43-bit sum (combinational from registered acc_fx).
            logic [42:0] mag;
            logic [5:0]  e2;
            logic [8:0]  bexp;
            logic [23:0] sig24;
            logic [24:0] sig25;
            logic [42:0] rest;
            logic [5:0]  shift;
            logic        round_bit, sticky, bump;
            integer      bi;

            always_comb begin
                bi        = 0;
                fp32      = 32'd0;
                mag       = 43'd0;
                e2        = 6'd0;
                bexp      = 9'd0;
                sig24     = 24'd0;
                sig25     = 25'd0;
                rest      = 43'd0;
                shift     = 6'd0;
                round_bit = 1'b0;
                sticky    = 1'b0;
                bump      = 1'b0;
                if (poison) begin
                    fp32 = CANON_NAN;
                end else if (acc_fx == 43'sd0) begin
                    fp32 = all_neg0 ? FP32_NEG0 : 32'd0;
                end else begin
                    mag = acc_fx[42] ? -acc_fx : acc_fx;
                    e2  = 6'd0;
                    for (bi = 0; bi < 43; bi = bi + 1) begin
                        if (mag[bi])
                            e2 = bi[5:0];
                    end
                    bexp = {3'b0, e2} + 9'd109; // (e2 - 18) + 127
                    if (e2 <= 6'd23) begin
                        sig24 = mag[23:0] << (6'd23 - e2);
                    end else begin
                        shift     = e2 - 6'd23;
                        sig24     = 24'(mag >> shift);
                        rest      = mag & ((43'd1 << shift) - 43'd1);
                        round_bit = |( (rest >> (shift - 6'd1)) & 43'd1 );
                        sticky    = |(rest & ((43'd1 << (shift - 6'd1)) - 43'd1));
                        if (TIE_UP)
                            bump = round_bit;
                        else
                            bump = round_bit && (sticky || sig24[0]);
                        if (bump) begin
                            sig25 = {1'b0, sig24} + 25'd1;
                            if (sig25[24]) begin
                                sig24 = 24'h800000;
                                bexp  = bexp + 9'd1;
                            end else begin
                                sig24 = sig25[23:0];
                            end
                        end
                    end
                    fp32 = {acc_fx[42], bexp[7:0], sig24[22:0]};
                end
            end

            assign acc = $signed(fp32);
        end
    endgenerate
endmodule

`default_nettype wire
