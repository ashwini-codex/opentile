// Immediate assertions wrapping pe. Bound/proved by SymbiYosys (O6).
// Yosys 0.70 `read -formal` does not parse `bind`; use a wrapper top.
`default_nettype none

module pe_formal (
    input  logic              clk,
    input  logic              clr,
    input  logic              en,
    input  logic signed [7:0] a_in,
    input  logic signed [7:0] b_in,
    output logic signed [7:0] a_out,
    output logic signed [7:0] b_out,
    output logic signed [31:0] acc
);
    logic valid_o_nc;
    pe dut (
        .clk(clk),
        .clr(clr),
        .en(en),
        .valid(1'b1),
        .a_in(a_in),
        .b_in(b_in),
        .a_out(a_out),
        .b_out(b_out),
        .valid_o(valid_o_nc),
        .acc(acc)
    );

    logic signed [15:0] prod;
    assign prod = a_in * b_in;

    logic seen = 1'b0;
    logic clr_d = 1'b0, en_d = 1'b0;
    logic signed [7:0] a_in_d, b_in_d, a_out_d, b_out_d;
    logic signed [31:0] acc_d;
    logic signed [15:0] prod_d;

    always_ff @(posedge clk) begin
        seen    <= 1'b1;
        clr_d   <= clr;
        en_d    <= en;
        a_in_d  <= a_in;
        b_in_d  <= b_in;
        a_out_d <= a_out;
        b_out_d <= b_out;
        acc_d   <= acc;
        prod_d  <= prod;

        if (seen) begin
            if (clr_d) begin
                assert (acc == 32'sd0);
                assert (a_out == 8'sd0);
                assert (b_out == 8'sd0);
            end else if (!en_d) begin
                assert (acc == acc_d);
                assert (a_out == a_out_d);
                assert (b_out == b_out_d);
            end else begin
                assert (acc == acc_d + 32'(prod_d));
                assert (a_out == a_in_d);
                assert (b_out == b_in_d);
            end
        end

        cover (clr);
        cover (!clr && en);
        cover (!clr && !en);
        cover (!clr && en && a_in == -8'sd128 && b_in == -8'sd128);
    end
endmodule

`default_nettype wire
