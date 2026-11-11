// Deliberately broken PE: unsigned operand multiply (O6 failure demo).
`default_nettype none

module pe (
    input  logic              clk,
    input  logic              clr,
    input  logic              en,
    input  logic              valid,
    input  logic signed [7:0] a_in,
    input  logic signed [7:0] b_in,
    output logic signed [7:0] a_out,
    output logic signed [7:0] b_out,
    output logic              valid_o,
    output logic signed [31:0] acc
);
    logic [15:0] prod;
    assign prod = $unsigned(a_in) * $unsigned(b_in);

    always_ff @(posedge clk) begin
        if (clr) begin
            acc     <= 32'sd0;
            a_out   <= 8'sd0;
            b_out   <= 8'sd0;
            valid_o <= 1'b0;
        end else if (en) begin
            acc     <= acc + 32'(prod);
            a_out   <= a_in;
            b_out   <= b_in;
            valid_o <= valid;
        end
    end
endmodule

`default_nettype wire
