// Deliberately broken array: row 1 has no A skew (O7 failure demo).
`default_nettype none

module array #(
    parameter int        R   = 4,
    parameter int        C   = 4,
    parameter [31:0]     FMT = "INT8"
) (
    input  logic                     clk,
    input  logic                     clr,
    input  logic                     en,
    input  logic                     valid,
    input  logic [8*R-1:0]           a_vec,
    input  logic [8*C-1:0]           b_vec,
    output logic [32*R*C-1:0]        acc_o
);
    logic signed [7:0] a_el [0:R-1];
    logic signed [7:0] b_el [0:C-1];
    logic signed [7:0] a_sk [0:R-1];
    logic signed [7:0] b_sk [0:C-1];
    logic signed [7:0] a_h  [0:R-1][0:C];
    logic signed [7:0] b_v  [0:R][0:C-1];
    logic signed [31:0] acc [0:R-1][0:C-1];
    logic              v_nc [0:R-1][0:C-1];

    genvar gi, gj, gp;

    generate
        for (gi = 0; gi < R; gi++) begin : g_a_el
            assign a_el[gi] = signed'(a_vec[8*gi +: 8]);
        end
        for (gj = 0; gj < C; gj++) begin : g_b_el
            assign b_el[gj] = signed'(b_vec[8*gj +: 8]);
        end
    endgenerate

    assign a_sk[0] = a_el[0];
    assign b_sk[0] = b_el[0];

    generate
        if (R > 1) begin : g_row_skew
            for (gi = 1; gi < R; gi++) begin : g_row
                logic signed [7:0] pipe [0:gi-1];
                for (gp = 0; gp < gi; gp++) begin : g_rp
                    if (gp == 0) begin : g_r0
                        always_ff @(posedge clk) begin
                            if (clr)       pipe[0] <= 8'sd0;
                            else if (en)   pipe[0] <= a_el[gi];
                        end
                    end else begin : g_rn
                        always_ff @(posedge clk) begin
                            if (clr)       pipe[gp] <= 8'sd0;
                            else if (en)   pipe[gp] <= pipe[gp-1];
                        end
                    end
                end
                // BUG: row 1 takes A with no delay.
                if (gi == 1) begin : g_bypass
                    assign a_sk[gi] = a_el[gi];
                end else begin : g_ok
                    assign a_sk[gi] = pipe[gi-1];
                end
            end
        end
        if (C > 1) begin : g_col_skew
            for (gj = 1; gj < C; gj++) begin : g_col
                logic signed [7:0] pipe [0:gj-1];
                for (gp = 0; gp < gj; gp++) begin : g_cp
                    if (gp == 0) begin : g_c0
                        always_ff @(posedge clk) begin
                            if (clr)       pipe[0] <= 8'sd0;
                            else if (en)   pipe[0] <= b_el[gj];
                        end
                    end else begin : g_cn
                        always_ff @(posedge clk) begin
                            if (clr)       pipe[gp] <= 8'sd0;
                            else if (en)   pipe[gp] <= pipe[gp-1];
                        end
                    end
                end
                assign b_sk[gj] = pipe[gj-1];
            end
        end
    endgenerate

    generate
        for (gi = 0; gi < R; gi++) begin : g_row_pe
            assign a_h[gi][0] = a_sk[gi];
            for (gj = 0; gj < C; gj++) begin : g_col_pe
                if (gi == 0) begin : g_north
                    assign b_v[0][gj] = b_sk[gj];
                end
                pe #(.FMT(FMT)) u_pe (
                    .clk     (clk),
                    .clr     (clr),
                    .en      (en),
                    .valid   (valid),
                    .a_in    (a_h[gi][gj]),
                    .b_in    (b_v[gi][gj]),
                    .a_out   (a_h[gi][gj+1]),
                    .b_out   (b_v[gi+1][gj]),
                    .valid_o (v_nc[gi][gj]),
                    .acc     (acc[gi][gj])
                );
                assign acc_o[32*(gi*C+gj) +: 32] = acc[gi][gj];
            end
        end
    endgenerate
endmodule

`default_nettype wire
